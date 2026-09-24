"""One request per process. Only package-owned operations may load skill code."""

import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

BRIDGE_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = BRIDGE_ROOT.parent
MAX_REQUEST_BYTES = 1024 * 1024

# -I excludes the script directory; only fixed package code supplies adapters.
sys.path.insert(0, str(BRIDGE_ROOT))
import skill_compat


class BridgeError(Exception):
    def __init__(self, code):
        self.code = code


class DiscardDiagnostics:
    """Do not retain or forward arbitrary upstream prints or exception details."""
    def write(self, value):
        return len(value)

    def flush(self):
        pass


def load_packaged_module(relative_path):
    target = RUNTIME_ROOT
    for part in relative_path.split('/'):
        if part in ('', '.', '..'):
            raise BridgeError('RUNTIME_MISSING')
        target = target / part
        if target.is_symlink():
            raise BridgeError('RUNTIME_MISSING')
    if not target.is_file() or not target.resolve().is_relative_to(RUNTIME_ROOT):
        raise BridgeError('RUNTIME_MISSING')
    spec = importlib.util.spec_from_file_location('ifly_packaged_skill', target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Legacy modules may sys.exit when imports fail. Classify import-time exits
    # separately, without parsing the human-readable diagnostic text.
    try:
        spec.loader.exec_module(module)
    except (ImportError, SystemExit) as error:
        raise BridgeError('DEPENDENCY_MISSING') from error
    return module


def list_voices(request):
    """Read bundled voice constants; does not authenticate or synthesize speech."""
    if set(request['input']) - {'files'} or request['input'].get('files') or request['parameters']:
        raise BridgeError('INVALID_INPUT')
    skill = load_packaged_module('skills/iflytek-hyper-tts/scripts/xfei_hyper_tts.py')
    return {'defaultVoice': skill.DEFAULT_VOICE, 'freeVoices': skill.FREE_VOICES, 'voices': skill.VOICE_LIST}, []


def _parameters(request):
    parameters = request['parameters']
    if not isinstance(parameters, dict):
        raise BridgeError('INVALID_INPUT')
    return parameters


def _text(request):
    value = request['input'].get('text')
    if isinstance(value, str):
        text = value
    elif value is None and isinstance(request['input'].get('files'), dict):
        relative = request['input']['files'].get('text')
        text = _read_file(relative, encoding='utf-8')
    else:
        raise BridgeError('INVALID_INPUT')
    if not text.strip() or len(text.encode('utf-8')) > 1024 * 1024:
        raise BridgeError('INVALID_INPUT')
    return text


def _read_file(relative, encoding=None):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise BridgeError('INVALID_INPUT')
    root = Path(os.environ.get('TMP', '')).resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise BridgeError('INVALID_INPUT')
    if not target.is_file() or target.is_symlink():
        raise BridgeError('INVALID_INPUT')
    try:
        data = target.read_bytes()
        return data.decode(encoding) if encoding else data
    except (OSError, UnicodeError):
        raise BridgeError('INVALID_INPUT')


def translate(request):
    skill = load_packaged_module('skills/iflytek-translate/scripts/translate.py')
    text = _text(request)
    parameters = _parameters(request)
    from_lang_value = parameters.get('fromLanguage', 'cn')
    to_lang_value = parameters.get('toLanguage', 'en')
    if not isinstance(from_lang_value, str) or not isinstance(to_lang_value, str):
        raise BridgeError('INVALID_INPUT')
    from_lang = skill._normalize_lang(from_lang_value)
    to_lang = skill._normalize_lang(to_lang_value)
    if not from_lang or not to_lang:
        raise BridgeError('INVALID_INPUT')
    try:
        body = skill._build_body(os.environ['IFLY_APP_ID'], text, from_lang, to_lang)
        response = skill._http_post(skill.URL, body, skill._build_headers(
            os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET'], body))
        parsed, error = skill._parse_result(response)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    if parsed is None or error:
        raise BridgeError('UPSTREAM_ERROR')
    return {'sourceText': parsed.get('src', ''), 'translatedText': parsed.get('dst', ''),
            'sourceLanguage': parsed.get('from', from_lang), 'targetLanguage': parsed.get('to', to_lang)}, []


def proofread(request):
    skill = load_packaged_module('skills/iflytek-text-proofread/scripts/text_proofread.py')
    text = _text(request)
    try:
        auth_url = skill._build_auth_url(skill.API_URL, os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET'])
        response = skill_compat.proofread_post(skill, auth_url, skill._build_body(os.environ['IFLY_APP_ID'], text), os.environ['IFLY_APP_ID'])
        result = skill._parse_result(response)
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    if not isinstance(result, dict) or result.get('error') or result.get('code') != 200:
        raise BridgeError('UPSTREAM_ERROR')
    return {'result': result}, []


def recognize_invoice(request):
    skill = load_packaged_module('skills/iflytek-ocr-invoice/scripts/invoice.py')
    files = request['input'].get('files')
    if not isinstance(files, dict) or 'image' not in files:
        raise BridgeError('INVALID_INPUT')
    path = _invoice_input_path(files['image'])
    try:
        raw = skill.recognize_invoice(path, os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET'])
        extracted = skill.extract_result(raw)
        try:
            result = json.loads(extracted)
        except (TypeError, json.JSONDecodeError):
            result = extracted
    except BridgeError:
        raise
    except (Exception, SystemExit) as error:
        # The original CLI exits on HTTP/connection errors; keep node failures
        # within the upstream error contract without changing the Skill.
        raise BridgeError('UPSTREAM_ERROR') from error
    if isinstance(result, str) and result.startswith(('API Error', 'Unexpected response')):
        raise BridgeError('UPSTREAM_ERROR')
    return {'result': result}, []


def _file_path(relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise BridgeError('INVALID_INPUT')
    root = Path(os.environ.get('TMP', '')).resolve()
    target = (root / relative).resolve()
    if ((target != root and root not in target.parents) or not target.is_file() or target.is_symlink()):
        raise BridgeError('INVALID_INPUT')
    return str(target)


def _invoice_input_path(relative):
    source = Path(_file_path(relative))
    try:
        header = source.read_bytes()[:16]
    except OSError:
        raise BridgeError('INVALID_INPUT')
    if header.startswith(b'%PDF'):
        suffix = '.pdf'
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        suffix = '.png'
    elif header.startswith(b'\xff\xd8\xff'):
        suffix = '.jpg'
    elif header.startswith((b'GIF87a', b'GIF89a')):
        suffix = '.gif'
    elif header.startswith(b'BM'):
        suffix = '.bmp'
    elif header[:4] in (b'II*\x00', b'MM\x00*'):
        suffix = '.tif'
    else:
        suffix = '.jpg'
    target = source.parent / ('invoice-input' + suffix)
    try:
        shutil.copyfile(source, target)
    except OSError:
        raise BridgeError('INVALID_INPUT')
    return str(target)


def _copy_input_with_suffix(relative, suffix, prefix):
    """Copy a runner input into the extension expected by a legacy Skill."""
    source = Path(_file_path(relative))
    target = source.parent / (prefix + suffix)
    try:
        shutil.copyfile(source, target)
    except OSError:
        raise BridgeError('INVALID_INPUT')
    return str(target)


def _image_input_path(relative, prefix='image-input'):
    source = Path(_file_path(relative))
    try:
        header = source.read_bytes()[:16]
    except OSError:
        raise BridgeError('INVALID_INPUT')
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        suffix = '.png'
    elif header.startswith(b'\xff\xd8\xff'):
        suffix = '.jpg'
    elif header.startswith((b'GIF87a', b'GIF89a')):
        suffix = '.gif'
    elif header.startswith(b'BM'):
        suffix = '.bmp'
    elif header[:4] in (b'II*\x00', b'MM\x00*'):
        suffix = '.tif'
    else:
        raise BridgeError('INVALID_INPUT')
    return _copy_input_with_suffix(relative, suffix, prefix)


def _pdf_input_path(relative):
    source = Path(_file_path(relative))
    try:
        if not source.read_bytes()[:5].startswith(b'%PDF-'):
            raise BridgeError('INVALID_INPUT')
    except BridgeError:
        raise
    except OSError:
        raise BridgeError('INVALID_INPUT')
    return _copy_input_with_suffix(relative, '.pdf', 'pdf-input')


def _task_no(request, name):
    value = _parameters(request).get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise BridgeError('INVALID_INPUT')
    return value.strip()


def recognize_image(request):
    skill = load_packaged_module('skills/iflytek-pdf-image-ocr/scripts/image_ocr.py')
    files = request['input'].get('files')
    if not isinstance(files, dict) or 'image' not in files:
        raise BridgeError('INVALID_INPUT')
    parameters = _parameters(request)
    result_format = parameters.get('resultFormat', 'json,markdown')
    if result_format not in ('json', 'markdown', 'json,markdown'):
        raise BridgeError('INVALID_INPUT')
    path = _image_input_path(files['image'])
    try:
        result = skill_compat.image_ocr_client(skill,
            os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET']
        ).ocr(path, result_format)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'result': result}, []


def create_pdf_task(request):
    skill = load_packaged_module('skills/iflytek-pdf-image-ocr/scripts/pdf_ocr.py')
    parameters = _parameters(request)
    export_format = parameters.get('exportFormat', 'word')
    pdf_url = parameters.get('pdfUrl', '')
    files = request['input'].get('files')
    if export_format not in ('word', 'markdown', 'json') or not isinstance(pdf_url, str):
        raise BridgeError('INVALID_INPUT')
    if pdf_url and (len(pdf_url) > 2048 or not pdf_url.startswith(('http://', 'https://'))):
        raise BridgeError('INVALID_INPUT')
    pdf_path = None
    if isinstance(files, dict) and files.get('pdf'):
        pdf_path = Path(_pdf_input_path(files['pdf']))
    if pdf_path and pdf_url:
        raise BridgeError('INVALID_INPUT')
    if not pdf_path and not pdf_url:
        raise BridgeError('INVALID_INPUT')
    try:
        result = skill.IflyPdfOCRClient(
            os.environ['IFLY_APP_ID'], os.environ['IFLY_API_SECRET']
        ).start_task(pdf_path=pdf_path, pdf_url=pdf_url or None, export_format=export_format)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    data = result.get('data', {}) if isinstance(result, dict) else {}
    return {'result': result, 'taskNo': data.get('taskNo'), 'status': data.get('status')}, []


def query_pdf_task(request):
    skill = load_packaged_module('skills/iflytek-pdf-image-ocr/scripts/pdf_ocr.py')
    task_no = _task_no(request, 'taskNo')
    try:
        result = skill.IflyPdfOCRClient(
            os.environ['IFLY_APP_ID'], os.environ['IFLY_API_SECRET']
        ).query_status(task_no)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    data = result.get('data', {}) if isinstance(result, dict) else {}
    status = data.get('status')
    return {
        'result': result, 'taskNo': task_no, 'status': status,
        'completed': status in ('FINISH', 'ANY_FAILED'),
    }, []


def _audio_input_path(relative):
    return _copy_input_with_suffix(relative, '.mp3', 'audio-input')


def _transcription_parameters(parameters):
    allowed = {'language', 'accent', 'domain', 'callbackUrl', 'vsppOn', 'speakerNum',
               'outputType', 'postprocOn', 'pd', 'enableSubtitle', 'smoothproc',
               'colloqproc', 'languageType', 'vto', 'dhw'}
    if set(parameters) - allowed:
        raise BridgeError('INVALID_INPUT')
    mapping = {
        'callbackUrl': 'callback_url', 'vsppOn': 'vspp_on', 'speakerNum': 'speaker_num',
        'outputType': 'output_type', 'postprocOn': 'postproc_on',
        'enableSubtitle': 'enable_subtitle', 'languageType': 'language_type',
        'smoothproc': 'smoothproc', 'colloqproc': 'colloqproc',
    }
    values = {}
    for key, value in parameters.items():
        target = mapping.get(key, key)
        if target in ('language', 'accent', 'domain', 'callback_url', 'pd', 'dhw'):
            if not isinstance(value, str) or len(value) > 256:
                raise BridgeError('INVALID_INPUT')
        elif target in ('vspp_on', 'speaker_num', 'output_type', 'postproc_on', 'enable_subtitle', 'language_type', 'vto'):
            if type(value) is not int:
                raise BridgeError('INVALID_INPUT')
        elif target in ('smoothproc', 'colloqproc') and type(value) is not bool:
            raise BridgeError('INVALID_INPUT')
        values[target] = value
    return values


def create_transcription_task(request):
    skill = load_packaged_module('skills/iflytek-speed-transcription/scripts/transcribe.py')
    files = request['input'].get('files')
    if not isinstance(files, dict) or 'audio' not in files:
        raise BridgeError('INVALID_INPUT')
    path = _audio_input_path(files['audio'])
    parameters = _transcription_parameters(_parameters(request))
    try:
        client = skill_compat.transcription_client(skill,
            os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET']
        )
        if Path(path).stat().st_size < 31457280:
            audio_url = client.upload_small_file(Path(path))
        else:
            audio_url = client.upload_large_file(Path(path))
        task_id = client.create_task(audio_url, file_path=Path(path), **parameters)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'taskId': task_id, 'audioUrl': audio_url}, []


def query_transcription_task(request, parse=False):
    skill = load_packaged_module('skills/iflytek-speed-transcription/scripts/transcribe.py')
    task_id = _task_no(request, 'taskId')
    try:
        client = skill_compat.transcription_client(skill,
            os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET']
        )
        raw = client.query_task(task_id)
        if parse:
            return client._parse_result(raw), []
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    data = raw.get('data', {}) if isinstance(raw, dict) else {}
    return {'taskId': task_id, 'status': data.get('task_status'), 'result': raw}, []


def get_transcription_task(request):
    return query_transcription_task(request, parse=False)


def get_transcription_result(request):
    return query_transcription_task(request, parse=True)


def analyze_image(request):
    skill = load_packaged_module('skills/iflytek-image-understanding/scripts/image_understanding.py')
    files = request['input'].get('files')
    if not isinstance(files, dict) or 'image' not in files:
        raise BridgeError('INVALID_INPUT')
    parameters = _parameters(request)
    question = parameters.get('question', 'Please describe this image in detail.')
    domain = parameters.get('domain', 'imagev3')
    temperature = parameters.get('temperature', 0.5)
    max_tokens = parameters.get('maxTokens', 2048)
    if (not isinstance(question, str) or not question.strip() or len(question.encode('utf-8')) > 1024 * 1024
            or domain not in ('general', 'imagev3') or type(temperature) not in (int, float)
            or not 0 < temperature <= 1 or type(max_tokens) is not int or not 1 <= max_tokens <= 8192):
        raise BridgeError('INVALID_INPUT')
    path = _image_input_path(files['image'], 'understanding-input')
    try:
        image = skill.read_image_base64(path)
        messages = [
            {'role': 'user', 'content': image, 'content_type': 'image'},
            {'role': 'user', 'content': question, 'content_type': 'text'},
        ]
        result = skill_compat.run_understanding(skill,
            os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET'],
            messages, domain, float(temperature), max_tokens, False,
        )
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'text': result}, []


def _url_parameter(parameters, name):
    value = parameters.get(name)
    if not isinstance(value, str) or not value.startswith(('http://', 'https://')) or len(value) > 2048:
        raise BridgeError('INVALID_INPUT')
    return value


def _remote_task_id(request, name):
    value = _task_no(request, name)
    if not all(character.isalnum() or character in '-_' for character in value):
        raise BridgeError('INVALID_INPUT')
    return value


def video_create_task(request):
    skill = load_packaged_module('skills/iflytek-video-translate/scripts/xfei_video_translate.py')
    parameters = _parameters(request)
    file_url = _url_parameter(parameters, 'fileUrl')
    source_language = parameters.get('sourceLanguage', 'en')
    target_language = parameters.get('targetLanguage', 'zh')
    task_name = parameters.get('taskName', '')
    if (not isinstance(source_language, str) or not source_language or len(source_language) > 32
            or not isinstance(target_language, str) or not target_language or len(target_language) > 32
            or not isinstance(task_name, str) or len(task_name) > 256):
        raise BridgeError('INVALID_INPUT')
    try:
        result = skill.XfeiVideoTranslateClient(
            os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET']
        ).create_task(file_url, source_language, target_language, task_name or None)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'result': result}, []


def video_list_tasks(request):
    if set(request['input']) - {'files'} or request['input'].get('files') or request['parameters']:
        raise BridgeError('INVALID_INPUT')
    skill = load_packaged_module('skills/iflytek-video-translate/scripts/xfei_video_translate.py')
    try:
        result = skill.XfeiVideoTranslateClient(
            os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET']
        ).list_tasks()
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'result': result}, []


def video_get_task(request):
    skill = load_packaged_module('skills/iflytek-video-translate/scripts/xfei_video_translate.py')
    task_id = _remote_task_id(request, 'taskId')
    try:
        result = skill.XfeiVideoTranslateClient(
            os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET']
        ).get_task(task_id)
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'taskId': task_id, 'result': result}, []


def video_confirm_transcript(request):
    skill = load_packaged_module('skills/iflytek-video-translate/scripts/xfei_video_translate.py')
    task_id = _remote_task_id(request, 'taskId')
    force_rerun = _parameters(request).get('forceRerun', False)
    if type(force_rerun) is not bool:
        raise BridgeError('INVALID_INPUT')
    try:
        result = skill.XfeiVideoTranslateClient(
            os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET']
        ).confirm_transcript(task_id, force_rerun=force_rerun)
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'taskId': task_id, 'forceRerun': force_rerun, 'result': result}, []


def _numeric_task_id(request):
    value = _parameters(request).get('taskId')
    if type(value) is not int or value <= 0 or value > 2 ** 53 - 1:
        raise BridgeError('INVALID_INPUT')
    return value


def _positive_int(parameters, name, fallback, maximum=2 ** 31 - 1):
    value = parameters.get(name, fallback)
    if type(value) is not int or value <= 0 or value > maximum:
        raise BridgeError('INVALID_INPUT')
    return value


def _voice_client(skill):
    return skill.TrainClient(os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'])


def _training_result(result):
    if (not isinstance(result, dict) or type(result.get('code')) is not int
            or result['code'] != 0 or result.get('flag') is not True):
        raise BridgeError('UPSTREAM_ERROR')
    return result


def voice_get_training_text(request):
    skill = load_packaged_module('skills/iflytek-voiceclone-tts/scripts/voiceclone.py')
    text_id = _positive_int(_parameters(request), 'textId', 5001)
    try:
        result = _training_result(_voice_client(skill).get_training_text(text_id))
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'textId': text_id, 'result': result}, []


def voice_create_training(request):
    skill = load_packaged_module('skills/iflytek-voiceclone-tts/scripts/voiceclone.py')
    parameters = _parameters(request)
    name = parameters.get('name', 'voice_clone_task')
    sex = parameters.get('sex', 'female')
    engine = parameters.get('engine', 'omni_v1')
    language = parameters.get('language', 'cn')
    resource_name = parameters.get('resourceName')
    callback_url = parameters.get('callbackUrl')
    if not isinstance(name, str) or not name or len(name) > 256 or not isinstance(engine, str) or not engine:
        raise BridgeError('INVALID_INPUT')
    if isinstance(sex, str):
        sex = {'male': 1, 'm': 1, 'female': 2, 'f': 2, '1': 1, '2': 2}.get(sex.lower())
    if sex not in (1, 2) or language not in ('cn', 'en', 'jp', 'ko', 'ru'):
        raise BridgeError('INVALID_INPUT')
    if resource_name is not None and (not isinstance(resource_name, str) or len(resource_name) > 256):
        raise BridgeError('INVALID_INPUT')
    if callback_url is not None and (not isinstance(callback_url, str) or len(callback_url) > 2048
                                      or not callback_url.startswith(('http://', 'https://'))):
        raise BridgeError('INVALID_INPUT')
    try:
        result = _training_result(_voice_client(skill).create_task(
            name=name, sex=sex, engine=engine, language=language,
            resource_name=resource_name or None, callback_url=callback_url or None,
        ))
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'result': result}, []


def _voice_audio_path(relative, audio_format):
    if audio_format not in ('wav', 'mp3', 'm4a', 'pcm'):
        raise BridgeError('INVALID_INPUT')
    return _copy_input_with_suffix(relative, '.' + audio_format, 'voice-sample')


def voice_upload_sample(request):
    skill = load_packaged_module('skills/iflytek-voiceclone-tts/scripts/voiceclone.py')
    parameters = _parameters(request)
    task_id = _numeric_task_id(request)
    text_id = _positive_int(parameters, 'textId', 5001)
    segment_id = _positive_int(parameters, 'segmentId', 1)
    audio_url = parameters.get('audioUrl', '')
    files = request['input'].get('files')
    if not isinstance(audio_url, str):
        raise BridgeError('INVALID_INPUT')
    if audio_url and (not audio_url.startswith(('http://', 'https://')) or len(audio_url) > 2048):
        raise BridgeError('INVALID_INPUT')
    has_file = isinstance(files, dict) and 'audio' in files
    if bool(audio_url) == has_file:
        raise BridgeError('INVALID_INPUT')
    if has_file and parameters.get('confirmBinarySubmission') is not True:
        raise BridgeError('INVALID_INPUT')
    if has_file and Path(_file_path(files['audio'])).stat().st_size > 3 * 1024 * 1024:
        raise BridgeError('INVALID_INPUT')
    try:
        client = _voice_client(skill)
        if audio_url:
            result = client.upload_audio_url(task_id, audio_url, text_id, segment_id)
        else:
            audio_format = parameters.get('audioFormat', 'wav')
            path = _voice_audio_path(files['audio'], audio_format)
            result = client.upload_audio_file(task_id, path, text_id, segment_id)
        result = _training_result(result)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'taskId': task_id, 'trainingSubmitted': has_file, 'result': result}, []


def voice_submit_training(request):
    skill = load_packaged_module('skills/iflytek-voiceclone-tts/scripts/voiceclone.py')
    task_id = _numeric_task_id(request)
    try:
        result = _training_result(_voice_client(skill).submit_task(task_id))
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return {'taskId': task_id, 'result': result}, []


def voice_get_training(request):
    skill = load_packaged_module('skills/iflytek-voiceclone-tts/scripts/voiceclone.py')
    task_id = _numeric_task_id(request)
    try:
        result = _training_result(_voice_client(skill).get_task_status(task_id))
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    data = result.get('data', {}) if isinstance(result, dict) else {}
    return {'taskId': task_id, 'status': data.get('trainStatus'), 'resourceId': data.get('assetId'), 'result': result}, []


def voice_synthesize(request):
    skill = load_packaged_module('skills/iflytek-voiceclone-tts/scripts/voiceclone.py')
    text = _text(request)
    parameters = _parameters(request)
    res_id = parameters.get('resId')
    output_format = parameters.get('format', 'mp3')
    volume = parameters.get('volume', 50)
    speed = parameters.get('speed', 50)
    pitch = parameters.get('pitch', 50)
    sample_rate = parameters.get('sampleRate', 24000)
    if not isinstance(res_id, str) or not res_id or len(res_id) > 256 or output_format not in ('mp3', 'pcm', 'speex', 'opus'):
        raise BridgeError('INVALID_INPUT')
    if any(type(value) is not int or value < 0 or value > 100 for value in (volume, speed, pitch)):
        raise BridgeError('INVALID_INPUT')
    if type(sample_rate) is not int or sample_rate not in (8000, 16000, 24000):
        raise BridgeError('INVALID_INPUT')
    output = Path(os.environ.get('TMP', '')) / ('voice-clone.' + output_format)
    args = SimpleNamespace(format=output_format, volume=volume, speed=speed, pitch=pitch, sample_rate=sample_rate)
    try:
        client = skill.VoiceCloneSynthesizer(
            os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET'], res_id, args)
        audio = skill_compat.voice_synthesize(skill, client, text)
        if not isinstance(audio, bytes) or not audio:
            raise BridgeError('INVALID_ARTIFACT')
        output.write_bytes(audio)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    mime_types = {'mp3': 'audio/mpeg', 'pcm': 'audio/L16', 'speex': 'audio/speex', 'opus': 'audio/opus'}
    return {'resId': res_id, 'format': output_format, 'bytes': len(audio)}, [{
        'relativePath': output.name, 'fileName': output.name, 'mimeType': mime_types[output_format],
    }]


def synthesize(request):
    skill = load_packaged_module('skills/iflytek-hyper-tts/scripts/xfei_hyper_tts.py')
    text = _text(request)
    parameters = _parameters(request)
    voice = parameters.get('voice', skill.DEFAULT_VOICE)
    speed = parameters.get('speed', 50)
    volume = parameters.get('volume', 50)
    pitch = parameters.get('pitch', 50)
    sample_rate = parameters.get('sampleRate', 24000)
    role = parameters.get('role')
    if not isinstance(voice, str) or not voice or any(type(value) is not int or value < 0 or value > 100
                                                       for value in (speed, volume, pitch)):
        raise BridgeError('INVALID_INPUT')
    if type(sample_rate) is not int or sample_rate not in (8000, 16000, 24000) or role is not None and not isinstance(role, str):
        raise BridgeError('INVALID_INPUT')
    output = Path(os.environ.get('TMP', '')) / 'speech.mp3'
    try:
        client = skill.XfeiHyperTTSClient(os.environ['IFLY_APP_ID'], os.environ['IFLY_API_KEY'], os.environ['IFLY_API_SECRET'])
        result = skill_compat.hyper_synthesize(skill, client, text=text, output_path=str(output), vcn=voice, speed=speed, volume=volume,
                                   pitch=pitch, encoding='lame', sample_rate=sample_rate, role=role)
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    if not output.is_file() or output.is_symlink():
        raise BridgeError('INVALID_ARTIFACT')
    result.pop('output_path', None)
    return result, [{'relativePath': 'speech.mp3', 'fileName': 'speech.mp3', 'mimeType': 'audio/mpeg'}]


def review_contract(request):
    parameters = _parameters(request)
    if set(parameters) - {'format', 'lang', 'reviewMode', 'focus', 'needTranslation', 'imageMethod'}:
        raise BridgeError('INVALID_INPUT')
    fmt = parameters.get('format', 'text')
    if fmt not in ('text', 'pdf', 'png', 'jpg', 'bmp', 'docx'):
        raise BridgeError('INVALID_INPUT')
    root = Path(os.environ['TMP'])
    target = root / ('contract.' + ('txt' if fmt == 'text' else fmt))
    if fmt == 'text':
        text = _text(request)
        if len(text) > 4000:
            raise BridgeError('INVALID_INPUT')
        target.write_text(text, encoding='utf-8')
    else:
        files = request['input'].get('files', {})
        source = Path(_file_path(files.get('document')))
        if source.stat().st_size > 20 * 1024 * 1024:
            raise BridgeError('INVALID_INPUT')
        with source.open('rb') as stream:
            header = stream.read(8)
        signatures = {'pdf': b'%PDF-', 'png': b'\x89PNG\r\n\x1a\n', 'jpg': b'\xff\xd8\xff',
                      'bmp': b'BM', 'docx': b'PK\x03\x04'}
        if not header.startswith(signatures[fmt]):
            raise BridgeError('INVALID_INPUT')
        shutil.copyfile(source, target)
    # -I excludes script directories. Only these fixed package directories supply imports.
    for directory in (BRIDGE_ROOT, RUNTIME_ROOT / 'skills/iflytek-contract-intelligence-review/scripts'):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    from contract import main as skill
    try:
        result = skill.run_review(
            input_path=str(target), lang=parameters.get('lang', 'zh'),
            review_mode=parameters.get('reviewMode', 'standard'), focus=parameters.get('focus', []),
            need_translation=parameters.get('needTranslation', False),
            output_dir=str(root), config=skill.Config(),
            image_method=parameters.get('imageMethod', 'ocr'))
    except ImportError:
        raise
    except (skill.InputValidationError, ValueError) as error:
        raise BridgeError('INVALID_INPUT') from error
    except Exception as error:
        raise BridgeError('UPSTREAM_ERROR') from error
    return result, [
        {'relativePath': 'contract_review_report.md', 'fileName': 'contract_review_report.md', 'mimeType': 'text/markdown'},
        {'relativePath': 'contract_review_result.json', 'fileName': 'contract_review_result.json', 'mimeType': 'application/json'},
    ]


def render_diagram(request):
    parameters = _parameters(request)
    if set(parameters) - {'width', 'height', 'fps', 'durationMs', 'scale'}:
        raise BridgeError('INVALID_INPUT')
    skill = load_packaged_module('bridge/diagram/render.py')
    try:
        result = skill.render_html(
            _text(request), os.environ['TMP'], width=parameters.get('width', 800),
            height=parameters.get('height', 500), fps=parameters.get('fps', 10),
            duration_ms=parameters.get('durationMs', 2000), scale=parameters.get('scale', 1))
    except ImportError:
        raise
    except ValueError as error:
        raise BridgeError('INVALID_INPUT') from error
    except Exception as error:
        raise BridgeError('PROCESS_EXIT') from error
    return result, [{'relativePath': 'diagram.gif', 'fileName': 'diagram.gif', 'mimeType': 'image/gif'}]


# Fixed dispatch table for packaged adapters; test adapters are excluded.
OPERATIONS = {
    ('iflytek-translate', 'translate'): translate,
    ('iflytek-text-proofread', 'check'): proofread,
    ('iflytek-ocr-invoice', 'recognize'): recognize_invoice,
    ('iflytek-hyper-tts', 'synthesize'): synthesize,
    ('iflytek-hyper-tts', 'listVoices'): list_voices,
    ('iflytek-pdf-image-ocr', 'recognizeImage'): recognize_image,
    ('iflytek-pdf-image-ocr', 'createPdfTask'): create_pdf_task,
    ('iflytek-pdf-image-ocr', 'getPdfTask'): query_pdf_task,
    ('iflytek-pdf-image-ocr', 'getResult'): query_pdf_task,
    ('iflytek-speed-transcription', 'createTask'): create_transcription_task,
    ('iflytek-speed-transcription', 'getTask'): get_transcription_task,
    ('iflytek-speed-transcription', 'getResult'): get_transcription_result,
    ('iflytek-image-understanding', 'analyze'): analyze_image,
    ('iflytek-video-translate', 'createTask'): video_create_task,
    ('iflytek-video-translate', 'listTasks'): video_list_tasks,
    ('iflytek-video-translate', 'getTask'): video_get_task,
    ('iflytek-video-translate', 'confirmTranscript'): video_confirm_transcript,
    ('iflytek-voiceclone-tts', 'getTrainingText'): voice_get_training_text,
    ('iflytek-voiceclone-tts', 'createTraining'): voice_create_training,
    ('iflytek-voiceclone-tts', 'uploadSample'): voice_upload_sample,
    ('iflytek-voiceclone-tts', 'submitTraining'): voice_submit_training,
    ('iflytek-voiceclone-tts', 'getTraining'): voice_get_training,
    ('iflytek-voiceclone-tts', 'synthesize'): voice_synthesize,
    ('iflytek-contract-intelligence-review', 'review'): review_contract,
    ('animated-sketch-diagram', 'renderHtmlToGif'): render_diagram,
}


def reject_constant(_value):
    raise BridgeError('INVALID_INPUT')


def main():
    started = time.monotonic()
    request_id = ''
    try:
        if len(sys.argv) != 5 or sys.argv[1] != '--skill' or sys.argv[3] != '--operation':
            raise BridgeError('INVALID_INPUT')
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(payload) > MAX_REQUEST_BYTES:
            raise BridgeError('INVALID_INPUT')
        request = json.loads(payload.decode('utf-8'), parse_constant=reject_constant)
        if not isinstance(request, dict) or request.get('protocolVersion') != 1:
            raise BridgeError('INVALID_INPUT')
        request_id = request.get('requestId', '')
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            request_id = ''
            raise BridgeError('INVALID_INPUT')
        if set(request) != {'protocolVersion', 'requestId', 'input', 'parameters'}:
            raise BridgeError('INVALID_INPUT')
        if not isinstance(request['input'], dict) or not isinstance(request['parameters'], dict):
            raise BridgeError('INVALID_INPUT')
        key = (sys.argv[2], sys.argv[4])
        manifest = json.loads((BRIDGE_ROOT / 'operations.json').read_text(encoding='utf-8'))
        entry = next((entry for entry in manifest['operations']
                      if (entry['skill'], entry['operation']) == key), None)
        if manifest['protocolVersion'] != 1 or entry is None or key not in OPERATIONS:
            raise BridgeError('UNSUPPORTED_OPERATION')
        fields = {'appId': 'IFLY_APP_ID', 'apiKey': 'IFLY_API_KEY', 'apiSecret': 'IFLY_API_SECRET'}
        if any(not os.environ.get(fields[field], '').strip() for field in entry['credentials']):
            raise BridgeError('AUTH_FAILED')
        with contextlib.redirect_stdout(DiscardDiagnostics()), contextlib.redirect_stderr(DiscardDiagnostics()):
            data, artifacts = OPERATIONS[key](request)
        response = {'protocolVersion': 1, 'requestId': request_id, 'ok': True,
                    'status': 'succeeded', 'data': data, 'artifacts': artifacts,
                    'meta': {'durationMs': round((time.monotonic() - started) * 1000)}}
        encoded = json.dumps(response, ensure_ascii=False, allow_nan=False)
    except BaseException as error:
        if isinstance(error, KeyboardInterrupt):
            code = 'EXECUTION_CANCELLED'
        elif isinstance(error, BridgeError):
            code = error.code
        elif isinstance(error, ImportError):
            code = 'DEPENDENCY_MISSING'
        elif isinstance(error, (ValueError, UnicodeError)):
            code = 'INVALID_INPUT'
        else:
            code = 'PROCESS_EXIT'
        response = {'protocolVersion': 1, 'requestId': request_id, 'ok': False,
                    'error': {'code': code, 'message': code, 'retryable': False}}
        encoded = json.dumps(response, ensure_ascii=False)
        sys.stdout.write(encoded + '\n')
        return 1
    sys.stdout.write(encoded + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
