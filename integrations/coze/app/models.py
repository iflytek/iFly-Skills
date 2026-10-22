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
    text: Text
    from_lang: Annotated[str, Field(min_length=1, max_length=32)] = "cn"
    to_lang: Annotated[str, Field(min_length=1, max_length=32)] = "en"

    @field_validator("text")
    @classmethod
    def length(cls, value):
        if not value.strip() or len(value.encode("utf-8")) > 4096:
            raise ValueError("Translation requires 1 to 4096 UTF-8 bytes")
        return value


class Translation(Model):
    src: str
    dst: str
    from_lang: str
    to_lang: str


class Proofread(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=220000)]


class Proofreading(Model):
    # Provider checklist entries vary by issue category; preserve its offsets and fields.
    checklist: list[dict]


class ImageInput(RequestModel):
    image_url: str


class Recognition(Model):
    result: dict | list


class ImageOCR(ImageInput):
    format: Literal["json", "markdown", "json,markdown"] = "json,markdown"


class OCRResult(Model):
    result: dict


class Speech(RequestModel):
    text: Text
    speed: Percent = 50
    volume: Percent = 50
    pitch: Percent = 50
    sample_rate: Literal[8000, 16000, 24000] = 24000

    @field_validator("text")
    @classmethod
    def length(cls, value):
        if not value.strip() or len(value.encode("utf-8")) > 65536:
            raise ValueError("Speech requires 1 to 65536 UTF-8 bytes")
        return value


class HyperSpeech(Speech):
    vcn: Identifier = "x5_lingxiaotang_flow"
    role: Annotated[str, Field(max_length=64)] | None = None


class CloneSpeech(Speech):
    res_id: Identifier
    format: Literal["mp3"] = "mp3"
    sample_rate: Literal[8000, 16000, 24000] = 16000


class Artifact(Model):
    artifact_id: str
    url: str
    mime_type: str
    size_bytes: int
    expires_at: str


class Audio(Model):
    audio: Artifact
    sample_rate: int
    format: Literal["mp3"] = "mp3"


class Voices(Model):
    free_voices: list[dict]
    all_voices: list[dict]


class PDFSubmission(Submission):
    pdf_url: str
    export_format: Literal["word", "markdown", "json"] = "word"


class PDFResult(Model):
    upstream_status: str
    details: dict = Field(default_factory=dict, description="Provider page-level results, including partial failures.")
    artifacts: list[Artifact] = Field(default_factory=list)


class TranscriptionSubmission(Submission):
    audio_url: str
    # This task type automatically recognizes Chinese and English. Other
    # combinations do not resolve to a supported service-side task type.
    language: Literal["zh_cn"] = "zh_cn"
    accent: Literal["mandarin"] = "mandarin"
    domain: Literal["pro_ost_ed"] = "pro_ost_ed"


class Segment(Model):
    speaker: str
    begin: str | int | float
    end: str | int | float
    text: str


class TranscriptionResult(Model):
    upstream_status: int
    text: str = ""
    segments: list[Segment] = Field(default_factory=list, description="Provider timestamps, retained without unit conversion.")


class Analyze(ImageInput):
    question: Annotated[str, Field(min_length=1, max_length=8192)]
    domain: Literal["general", "imagev3"] = "imagev3"
    temperature: Annotated[float, Field(gt=0, le=1)] = 0.5
    max_tokens: Annotated[int, Field(strict=True, ge=1, le=8192)] = 2048


class Analysis(Model):
    text: str
    usage: dict = Field(default_factory=dict)


class VideoSubmission(Submission):
    video_url: str
    src_lang: Identifier = "en"
    dest_lang: Identifier = "zh"
    name: Annotated[str, Field(max_length=256)] = ""


class TaskAction(Submission):
    job_id: JobId


class VideoResult(Model):
    upstream_status: str
    details: dict = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)


class TrainingSubmission(Submission):
    name: Annotated[str, Field(min_length=1, max_length=256)]
    sex: Literal[1, 2]
    engine: Literal["omni_v1"] = "omni_v1"
    language: Literal["cn", "en", "jp", "ko", "ru"] = "cn"
    resource_name: Annotated[str, Field(max_length=256)] | None = None


class UploadSample(TaskAction):
    audio_url: str
    text_id: Annotated[int, Field(strict=True, gt=0)] = 5001
    seg_id: Annotated[int, Field(strict=True, gt=0)] = 1


class TrainingText(Model):
    text_id: int
    segments: list[dict] | dict


class TrainingResult(Model):
    stage: Literal["created", "sample_uploaded", "submitted", "trained", "failed"]
    upstream_status: str | int | None = None
    res_id: str | None = None
    failure_reason: Literal["audio_text_mismatch"] | None = None


class Review(Submission):
    file_url: str
    lang: Literal["zh", "en", "bilingual"] = "zh"
    review_mode: Literal["quick", "standard", "deep"] = "standard"
    focus: list[Literal["payment", "liability", "renewal", "ip", "confidentiality", "dispute"]] = Field(default_factory=list, max_length=6)
    need_translation: bool = False
    output_format: Literal["markdown", "json", "both"] = "both"


class ReviewResult(Model):
    review: dict
    reports: list[Artifact]


class Render(Submission):
    html: Annotated[str, Field(min_length=1, max_length=262144)]
    width: Annotated[int, Field(strict=True, ge=64, le=1600)] = 800
    height: Annotated[int, Field(strict=True, ge=64, le=1200)] = 500
    fps: Annotated[int, Field(strict=True, ge=1, le=25)] = 25
    loop_ms: Annotated[int, Field(strict=True, ge=100, le=5000)] = 3000
    scale: Annotated[int, Field(strict=True, ge=1, le=2)] = 2

    @model_validator(mode="after")
    def budget(self):
        frames = (self.loop_ms * self.fps + 999) // 1000
        if (len(self.html.encode("utf-8")) > 262144
                or frames * self.width * self.height * self.scale ** 2 > 120_000_000):
            raise ValueError("Render exceeds the input or pixel-frame budget")
        return self


class RenderResult(Model):
    gif: Artifact
    width: int
    height: int
    frames: int
    fps: int


T = TypeVar("T")


class Job(Model, Generic[T]):
    job_id: JobId
    status: Literal["queued", "running", "waiting_input", "succeeded", "partially_succeeded", "failed", "submission_unknown"]
    result: T | None = None
    error_code: str | None = None
    poll_after_seconds: int = 5

    @model_validator(mode="after")
    def outcome(self):
        if self.status in {"succeeded", "partially_succeeded"} and self.result is None:
            raise ValueError("A completed task must have a result")
        if self.status in {"failed", "submission_unknown"} and not self.error_code:
            raise ValueError("An unsuccessful task must have an error code")
        return self
