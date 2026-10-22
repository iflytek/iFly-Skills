"""Contract OCR using the repository image OCR client."""
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from .iflytek import skill_module
from skill_compat import image_ocr_client

@dataclass
class OCRResult:
    text: str
    confidence: float | None
    regions: list
    page_count: int | None = 1

class OCRClient:
    def __init__(self, config):
        self.config = config

    def extract_text_from_image(self, image_path: str) -> str:
        self.config.require_credentials()
        if Path(image_path).stat().st_size > 4 * 1024 * 1024:
            raise ValueError("OCR image exceeds 4 MiB")
        module = skill_module("ocr")
        client = image_ocr_client(module, self.config.app_id, self.config.api_key, self.config.api_secret)
        result = client.ocr(image_path, result_format="markdown")
        text = result.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("OCR returned no text")
        return text

    def extract_text(self, file_path: str) -> str:
        self.config.require_credentials()
        import pypdfium2 as pdfium
        # Rasterize a bounded number of pages; no external result URL is downloaded.
        document = pdfium.PdfDocument(file_path)
        try:
            if not 1 <= len(document) <= self.config.max_pdf_pages:
                raise ValueError("PDF must contain 1 to 8 pages")
            parts = []
            with TemporaryDirectory(prefix="contract-pages-") as directory:
                for index in range(len(document)):
                    page = document[index]
                    bitmap = None
                    picture = None
                    try:
                        width, height = page.get_size()
                        if min(width, height) <= 0 or max(width, height) > 14400:
                            raise ValueError("Unsupported PDF page dimensions")
                        bitmap = page.render(scale=min(2, 1600 / max(width, height)))
                        picture = bitmap.to_pil()
                        target = Path(directory) / f"page-{index}.png"
                        picture.save(target)
                        parts.append(self.extract_text_from_image(str(target)))
                        target.unlink()
                        if len("\n".join(parts)) > self.config.max_input_chars:
                            raise ValueError("Contract exceeds 4000 characters; split it before review")
                    finally:
                        if picture is not None:
                            picture.close()
                        if bitmap is not None:
                            bitmap.close()
                        page.close()
            return "\n".join(parts)
        finally:
            document.close()

    def extract_with_details(self, file_path: str) -> OCRResult:
        is_pdf = Path(file_path).suffix.lower() == ".pdf"
        text = self.extract_text(file_path) if is_pdf else self.extract_text_from_image(file_path)
        return OCRResult(text=text, confidence=None, regions=[], page_count=None if is_pdf else 1)
