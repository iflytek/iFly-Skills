"""Public tool contracts. Credentials and local paths are never request fields."""

from typing import Annotated, Generic, Literal, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


Text = Annotated[str, Field(min_length=1)]
Identifier = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^\S+$")]
JobId = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Percent = Annotated[int, Field(strict=True, ge=0, le=100)]


class RequestModel(Model):
    @field_validator("*", mode="after")
    @classmethod
    def validate_urls(cls, value, info):
        if info.field_name.endswith("_url") and isinstance(value, str):
            parts = urlsplit(value)
            if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                    or parts.fragment or len(value) > 8192):
                raise ValueError("A public HTTPS URL is required")
        return value


class Submission(RequestModel):
    request_id: Identifier = Field(description="Stable idempotency key; reuse when retrying the same request.")


class Translate(RequestModel):
    text: Text = Field(description='Nonblank source text, at most 4096 UTF-8 bytes.')
    from_lang: Annotated[str, Field(min_length=1, max_length=32)] = Field("cn", description='Provider source language code, for example cn or en.')
    to_lang: Annotated[str, Field(min_length=1, max_length=32)] = Field("en", description='Provider target language code, for example en or cn.')

    @field_validator("text")
    @classmethod
    def length(cls, value):
        if not value.strip() or len(value.encode("utf-8")) > 4096:
            raise ValueError("Translation requires 1 to 4096 UTF-8 bytes")
        return value


class Translation(Model):
    src: str = Field(description='Source text returned by the provider.')
    dst: str = Field(description='Translated text.')
    from_lang: str = Field(description='Provider source language code, for example cn or en.')
    to_lang: str = Field(description='Provider target language code, for example en or cn.')


class Proofread(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=220000)] = Field(description='Chinese text to proofread; at most 220000 characters.')


class Proofreading(Model):
    # Provider checklist entries vary by issue category; preserve its offsets and fields.
    checklist: list[dict] = Field(description='Provider suggestions, issue categories and offsets in the original text.')


class ImageInput(RequestModel):
    image_url: str = Field(description='Public HTTPS PNG or JPEG URL, up to 4 MiB; not a local path or Coze file_id.')


class Recognition(Model):
    result: dict | list = Field(description='Structured invoice fields; provider layouts vary by invoice type.')


class ImageOCR(ImageInput):
    format: Literal["json", "markdown", "json,markdown"] = Field("json,markdown", description='Requested OCR output representation.')


class OCRResult(Model):
    result: dict = Field(description='Selected json and/or markdown entries from OCR.')


class Speech(RequestModel):
    text: Text = Field(description='Nonblank text to speak, at most 65536 UTF-8 bytes; provider limits also apply.')
    speed: Percent = Field(50, description='Speaking speed, 0 to 100; 50 is the default.')
    volume: Percent = Field(50, description='Speech volume, 0 to 100.')
    pitch: Percent = Field(50, description='Speech pitch, 0 to 100.')
    sample_rate: Literal[8000, 16000, 24000] = Field(24000, description='Output audio sample rate in Hz.')

    @field_validator("text")
    @classmethod
    def length(cls, value):
        if not value.strip() or len(value.encode("utf-8")) > 65536:
            raise ValueError("Speech requires 1 to 65536 UTF-8 bytes")
        return value


class HyperSpeech(Speech):
    vcn: Identifier = Field("x5_lingxiaotang_flow", description='Voice identifier from list_voices; account permission is required.')
    role: Annotated[str, Field(max_length=64)] | None = Field(None, description='Optional provider speaking role supported by the selected voice.')


class CloneSpeech(Speech):
    res_id: Identifier = Field(description='Voice resource ID from successful training in this workspace.')
    format: Literal["mp3"] = Field("mp3", description='Output encoding; this tool returns MP3 only.')
    sample_rate: Literal[8000, 16000, 24000] = Field(16000, description='Output audio sample rate in Hz.')


class Artifact(Model):
    artifact_id: str = Field(description='Opaque backend artifact identifier.')
    url: str = Field(description='Expiring HTTPS download URL; anyone holding it can download until expiration.')
    mime_type: str = Field(description='Artifact media type.')
    size_bytes: int = Field(description='Artifact size in bytes.')
    expires_at: str = Field(description='Expiration time in UTC, ISO 8601.')


class Audio(Model):
    audio: Artifact = Field(description='Complete synthesized audio and download information.')
    sample_rate: int = Field(description='Output audio sample rate in Hz.')
    format: Literal["mp3"] = Field("mp3", description='Audio encoding.')


class Voices(Model):
    free_voices: list[dict] = Field(description='Built-in entries marked free; verify account availability.')
    all_voices: list[dict] = Field(description='All built-in voice entries, including identifiers and attributes.')


class PDFSubmission(Submission):
    pdf_url: str = Field(description='Public HTTPS PDF URL, at most 32 MiB and 100 pages.')
    export_format: Literal["word", "markdown", "json"] = Field("word", description='Requested recognition export format.')


class PDFResult(Model):
    upstream_status: str = Field(description='Provider task status for the current stage, when available.')
    details: dict = Field(default_factory=dict, description="Provider page-level results, including partial failures.")
    artifacts: list[Artifact] = Field(default_factory=list, description='Available output files with expiring HTTPS URLs.')


class TranscriptionSubmission(Submission):
    audio_url: str = Field(description='Public HTTPS MP3 URL, up to 128 MiB.')
    # This task type automatically recognizes Chinese and English. Other
    # combinations do not resolve to a supported service-side task type.
    language: Literal["zh_cn"] = Field("zh_cn", description='Fixed provider setting for automatic Chinese and English recognition.')
    accent: Literal["mandarin"] = Field("mandarin", description='Required accent setting, including for English audio.')
    domain: Literal["pro_ost_ed"] = Field("pro_ost_ed", description='Required provider transcription task domain.')


class Segment(Model):
    speaker: str = Field(description='Provider speaker identifier.')
    begin: str | int | float = Field(description='Provider segment start timestamp; units are not converted.')
    end: str | int | float = Field(description='Provider segment end timestamp; units are not converted.')
    text: str = Field(description='Recognized segment text.')


class TranscriptionResult(Model):
    upstream_status: int = Field(description='Provider task status for the current stage, when available.')
    text: str = Field("", description='Full recognized text when available.')
    segments: list[Segment] = Field(default_factory=list, description="Provider timestamps, retained without unit conversion.")


class Analyze(ImageInput):
    question: Annotated[str, Field(min_length=1, max_length=8192)] = Field(description='Question to answer about the image.')
    domain: Literal["general", "imagev3"] = Field("imagev3", description='Provider image model domain.')
    temperature: Annotated[float, Field(gt=0, le=1)] = Field(0.5, description='Response sampling temperature, greater than 0 and at most 1.')
    max_tokens: Annotated[int, Field(strict=True, ge=1, le=8192)] = Field(2048, description='Maximum number of output tokens.')


class Analysis(Model):
    text: str = Field(description='Complete image analysis answer.')
    usage: dict = Field(default_factory=dict, description='Provider token usage details.')


class VideoSubmission(Submission):
    video_url: str = Field(description='Public HTTPS MP4 URL, up to 128 MiB.')
    src_lang: Identifier = Field("en", description='Provider source language code.')
    dest_lang: Identifier = Field("zh", description='Provider destination language code.')
    name: Annotated[str, Field(max_length=256)] = Field("", description='Optional video task name.')


class TaskAction(Submission):
    job_id: JobId = Field(description="Backend job ID returned by this workspace's creation operation.")


class VideoResult(Model):
    upstream_status: str = Field(description='Provider task status for the current stage, when available.')
    details: dict = Field(default_factory=dict, description='Available output or transcript segments for the current stage.')
    artifacts: list[Artifact] = Field(default_factory=list, description='Available output files with expiring HTTPS URLs.')


class TrainingSubmission(Submission):
    name: Annotated[str, Field(min_length=1, max_length=256)] = Field(description='Training task name.')
    sex: Literal[1, 2] = Field(description='Speaker voice setting: 1 for male, 2 for female.')
    engine: Literal["omni_v1"] = Field("omni_v1", description='Supported multi-style training engine.')
    language: Literal["cn", "en", "jp", "ko", "ru"] = Field("cn", description='Training recording language.')
    resource_name: Annotated[str, Field(max_length=256)] | None = Field(None, description='Optional voice resource name; task name is used when omitted.')


class UploadSample(TaskAction):
    audio_url: str = Field(description='HTTPS WAV (16 bit) or MP3: mono, at least 24 kHz, at most 40 seconds and 3 MiB; record the exact selected text with speaker authorization.')
    text_id: Annotated[int, Field(strict=True, gt=0)] = Field(5001, description='Provider training text set ID; 5001 is the common set.')
    seg_id: Annotated[int, Field(strict=True, gt=0)] = Field(1, description='Returned segment ID whose text exactly matches the recording.')


class TrainingText(Model):
    text_id: int = Field(description='Provider training text set ID; 5001 is the common set.')
    segments: list[dict] | dict = Field(description='Provider text set with segment IDs, exact recording texts and languages.')


class TrainingResult(Model):
    stage: Literal["created", "sample_uploaded", "submitted", "trained", "failed"] = Field(description='Current training workflow stage.')
    upstream_status: str | int | None = Field(None, description='Provider task status for the current stage, when available.')
    res_id: str | None = Field(None, description='Voice resource ID from successful training in this workspace.')
    failure_reason: Literal["audio_text_mismatch"] | None = Field(None, description='Known safe failure reason; null if unavailable.')


class Review(Submission):
    file_url: str = Field(description='Public HTTPS TXT, Markdown, DOCX, PDF, PNG or JPEG; at most 20 MiB, 8 PDF pages and 4000 extracted characters.')
    lang: Literal["zh", "en", "bilingual"] = Field("zh", description='Contract language; en also requests an English summary; bilingual enables bilingual clause checks.')
    review_mode: Literal["quick", "standard", "deep"] = Field("standard", description='Review depth; deep also requests an English summary.')
    focus: list[Literal["payment", "liability", "renewal", "ip", "confidentiality", "dispute"]] = Field(default_factory=list, max_length=6, description='Optional review focus categories.')
    need_translation: bool = Field(False, description='Request an English translated summary; required translation failure fails the review.')
    output_format: Literal["markdown", "json", "both"] = Field("both", description='Report formats to generate.')


class ReviewResult(Model):
    review: dict = Field(description='Structured rule findings, model review and available translated summary; requires human judgment.')
    reports: list[Artifact] = Field(description='Selected report formats with expiring HTTPS URLs.')


class Render(Submission):
    html: Annotated[str, Field(min_length=1, max_length=262144)] = Field(description='HTML/SVG/CSS animation, at most 256 KiB and 2000 elements; no scripts, external resources or local file references.')
    width: Annotated[int, Field(strict=True, ge=64, le=1600)] = Field(800, description='Viewport width in pixels before scale.')
    height: Annotated[int, Field(strict=True, ge=64, le=1200)] = Field(500, description='Viewport height in pixels before scale.')
    fps: Annotated[int, Field(strict=True, ge=1, le=25)] = Field(25, description='Animation frames per second.')
    loop_ms: Annotated[int, Field(strict=True, ge=100, le=5000)] = Field(3000, description='Animation duration in milliseconds.')
    scale: Annotated[int, Field(strict=True, ge=1, le=2)] = Field(2, description='Resolution multiplier; frames times width times height times scale squared must not exceed 120 million.')

    @model_validator(mode="after")
    def budget(self):
        frames = (self.loop_ms * self.fps + 999) // 1000
        if (len(self.html.encode("utf-8")) > 262144
                or frames * self.width * self.height * self.scale ** 2 > 120_000_000):
            raise ValueError("Render exceeds the input or pixel-frame budget")
        return self


class RenderResult(Model):
    gif: Artifact = Field(description='Rendered animated GIF with an expiring HTTPS URL.')
    width: int = Field(description='Rendered GIF width in pixels.')
    height: int = Field(description='Rendered GIF height in pixels.')
    frames: int = Field(description='Rendered frame count.')
    fps: int = Field(description='Animation frames per second.')


T = TypeVar("T")


class Job(Model, Generic[T]):
    job_id: JobId = Field(description="Backend job ID returned by this workspace's creation operation.")
    status: Literal["queued", "running", "waiting_input", "succeeded", "partially_succeeded", "failed", "submission_unknown"] = Field(description='Task state; HTTP 200 alone does not mean completion. waiting_input needs an explicit stage action; do not blindly resubmit submission_unknown.')
    result: T | None = Field(None, description='Current stage details or final result; null before a result is available.')
    error_code: str | None = Field(None, description='Safe error category for failed or uncertain tasks, otherwise null.')
    poll_after_seconds: int = Field(5, description='Minimum suggested interval before the next query; use bounded polling.')

    @model_validator(mode="after")
    def outcome(self):
        if self.status in {"succeeded", "partially_succeeded"} and self.result is None:
            raise ValueError("A completed task must have a result")
        if self.status in {"failed", "submission_unknown"} and not self.error_code:
            raise ValueError("An unsuccessful task must have an error code")
        return self
