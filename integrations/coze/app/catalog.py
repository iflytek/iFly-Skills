"""Closed tool inventory. Entries alone never register HTTP endpoints."""

from dataclasses import dataclass
from types import MappingProxyType


SKILL_TOOLS = MappingProxyType({
    "iflytek-translate": ("translate",),
    "iflytek-text-proofread": ("check",),
    "iflytek-ocr-invoice": ("recognize",),
    "iflytek-hyper-tts": ("synthesize", "list_voices"),
    "iflytek-pdf-image-ocr": ("recognize_image", "create_pdf_task", "get_pdf_task"),
    "iflytek-speed-transcription": ("create_task", "get_task"),
    "iflytek-image-understanding": ("analyze",),
    "iflytek-video-translate": ("create_task", "get_task", "confirm_transcript"),
    "iflytek-voiceclone-tts": (
        "get_training_text", "create_training", "upload_sample", "submit_training", "get_training", "synthesize",
    ),
    "iflytek-contract-intelligence-review": ("review", "get_review"),
    "animated-sketch-diagram": ("render_html_to_gif", "get_render"),
})
SKILL_IDS = frozenset(SKILL_TOOLS)


@dataclass(frozen=True)
class Tool:
    skill_id: str
    action: str

    def __post_init__(self):
        if self.action not in SKILL_TOOLS.get(self.skill_id, ()):
            raise ValueError("Tool is not in the Coze skill inventory")

    @property
    def path(self) -> str:
        return f"/v1/skills/{self.skill_id}/{self.action}"

    @property
    def method(self) -> str:
        return "GET" if self.action.startswith("get_") or self.action == "list_voices" else "POST"

    @property
    def operation_id(self) -> str:
        return f"{self.skill_id.replace('-', '_')}__{self.action}"
