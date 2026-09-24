"""Translation with the existing signed iFLYTEK text translation client."""
from dataclasses import dataclass
from .iflytek import skill_module

@dataclass
class TranslationResult:
    translated_text: str
    source_lang: str
    target_lang: str
    confidence: float | None = None

@dataclass
class BilingualSegment:
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    match_confidence: float | None = None

class TranslateClient:
    def __init__(self, config):
        self.config = config

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        self.config.require_credentials()
        if not text.strip() or len(text) > self.config.max_input_chars:
            raise ValueError("Invalid translation text")
        module = skill_module("translate")
        source = module._normalize_lang(source_lang)
        target = module._normalize_lang(target_lang)
        chunks, current, size = [], "", 0
        for character in text:
            length = len(character.encode("utf-8"))
            if size + length > 1800:
                chunks.append(current)
                current, size = "", 0
            current += character
            size += length
        if current:
            chunks.append(current)
        translated = []
        for chunk in chunks:
            body = module._build_body(self.config.app_id, chunk, source, target)
            headers = module._build_headers(self.config.api_key, self.config.api_secret, body)
            response = module._http_post(module.URL, body, headers, timeout=self.config.timeout)
            result, error = module._parse_result(response)
            if error or not result or not isinstance(result.get("dst"), str):
                raise RuntimeError("Contract translation failed")
            translated.append(result["dst"])
        return TranslationResult("".join(translated), source_lang, target_lang)

    def translate_summary(self, text: str, target_lang: str = "zh") -> str:
        source = "en" if target_lang == "zh" else "zh"
        return self.translate(text, source, target_lang).translated_text

    def create_bilingual_segments(self, source_text, target_text, source_lang, target_lang):
        # Keep the provided pair intact; semantic alignment is not inferred here.
        return [BilingualSegment(source_text, target_text, source_lang, target_lang)]