"""Compose the original contract processors within the n8n execution boundary."""
import json
from pathlib import Path

from .config import Config
from .clients.ocr_client import OCRClient
from .clients.image_client import ImageClient
from .clients.translate_client import TranslateClient
from .clients.llm_review_client import LLMReviewClient
from errors import InputValidationError
from processors.text_cleaner import TextCleaner
from processors.clause_splitter import ClauseSplitter
from processors.risk_detector import RiskDetector
from processors.compliance_checker import ComplianceChecker
from processors.bilingual_checker import BilingualChecker
from .report import ReportBuilder
from utils.file_utils import load_input_file


def extract(file_path, config, image_method):
    suffix = file_path.suffix.lower()
    if suffix == '.pdf':
        return OCRClient(config).extract_text(str(file_path)), 'pdf', 'ocr'
    if suffix in ('.png', '.jpg', '.bmp'):
        if image_method == 'understanding':
            return ImageClient(config).understand_image(str(file_path)), 'image', 'image_understanding_inference'
        return OCRClient(config).extract_text_from_image(str(file_path)), 'image', 'ocr'
    if suffix == '.docx':
        from docx import Document
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        from zipfile import ZipFile
        with ZipFile(file_path) as archive:
            if len(archive.infolist()) > 2000 or sum(item.file_size for item in archive.infolist()) > 32 * 1024 * 1024:
                raise InputValidationError('DOCX exceeds the extraction limit')
        parts = []
        for block in Document(file_path).iter_inner_content():
            if isinstance(block, Paragraph):
                parts.append(block.text)
            elif isinstance(block, Table):
                parts.extend(' | '.join(cell.text for cell in row.cells) for row in block.rows)
        return '\n'.join(parts), 'word', 'docx_extract'
    if suffix == '.txt':
        return load_input_file(file_path), 'text', 'direct_extract'
    raise InputValidationError('Unsupported contract format')


def run_review(input_path, lang, review_mode, focus, need_translation, output_dir,
               config=None, image_method='ocr'):
    config = config or Config()
    config.require_credentials()
    if (lang not in ('zh', 'en', 'bilingual') or review_mode not in ('quick', 'standard', 'deep')
            or image_method not in ('ocr', 'understanding') or type(need_translation) is not bool
            or not isinstance(focus, list)
            or any(item not in ('payment', 'liability', 'renewal', 'ip', 'confidentiality', 'dispute') for item in focus)):
        raise InputValidationError('Invalid contract options')
    source = Path(input_path)
    if not 0 < source.stat().st_size <= 20 * 1024 * 1024:
        raise InputValidationError('Contract exceeds the input limit')
    extracted, input_type, extraction_method = extract(source, config, image_method)
    if not extracted.strip() or len(extracted) > config.max_input_chars:
        raise InputValidationError('Contract must contain 1 to 4000 characters')

    # Reuse the Skill processors without changing their rules or CLI behavior.
    text = TextCleaner().clean(extracted)
    clauses = ClauseSplitter().split(text)
    detector = RiskDetector()
    risks = detector.detect(clauses, focus, review_mode)
    compliance = ComplianceChecker().check(clauses)
    bilingual = BilingualChecker().check(clauses) if lang == 'bilingual' or need_translation else []
    model = LLMReviewClient(config).review_contract(text, review_mode, focus)
    translation = TranslateClient(config).translate_summary(model.summary, target_lang='en') if need_translation else None
    result = {
        'document_meta': {'filename': source.name, 'input_type': input_type,
                          'extraction_method': extraction_method, 'language': lang,
                          'review_mode': review_mode, 'focus': focus or ['all']},
        'extraction_quality': {'text_length': len(text), 'confidence': None,
                               'uncertain_regions': detector.get_uncertain_regions()},
        'clauses': clauses, 'risks': risks + model.risks, 'compliance_issues': compliance,
        'bilingual_issues': bilingual, 'translation_summary': translation,
        'model_review': {'summary': model.summary, 'key_clauses': model.key_clauses,
                         'suggestions': model.suggestions, 'source': 'model_inference'},
        'check_methods': {'compliance': 'local_rules', 'bilingual': 'local_rules'},
        'uncertain_items': detector.get_uncertain_items(),
        'human_review_required': detector.get_human_review_flags() + [
            '规则检查和模型推断仅供辅助，需人工核对原文、法律适用和审核结论。'],
    }
    result['final_summary'] = ReportBuilder.generate_summary(result)
    # Extend the original report only with information specific to this adapter.
    report = ReportBuilder().build_markdown(result)
    report += '\n\n## 模型审阅（推断，需人工复核）\n\n' + model.summary + '\n\n'
    report += '\n'.join('- ' + item for item in model.key_clauses)
    report += '\n' + '\n'.join('- 建议: ' + item for item in model.suggestions) + '\n'
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'contract_review_report.md').write_text(report, encoding='utf-8')
    (output / 'contract_review_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
