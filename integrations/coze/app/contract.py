"""Contract workflow: original rules plus concrete OCR, image, translation and Spark clients."""

from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

from .adapters import SKILLS_ROOT, analyze, artifact_store, credentials, image_ocr, translate
from .contract_llm import LLMReviewClient
from .errors import ErrorCode, ServiceError
from .media import input_file


class OCRClient:
    def __init__(self, creds):
        self.creds = creds

    def image(self, path):
        return image_ocr(path, "markdown", self.creds, allow_empty=True)["markdown"]

    def pdf(self, path):
        import pypdfium2 as pdfium
        parts = []
        with pdfium.PdfDocument(path) as pdf, tempfile.TemporaryDirectory(prefix="contract-pages-") as directory:
            if not 1 <= len(pdf) <= 8:
                raise ServiceError(ErrorCode.INVALID_REQUEST)
            for index in range(len(pdf)):
                with pdf[index] as page:
                    width, height = page.get_size()
                    if min(width, height) <= 0 or max(width, height) > 14400:
                        raise ServiceError(ErrorCode.INVALID_REQUEST)
                    bitmap = page.render(scale=min(2, 1600 / max(width, height)))
                    try:
                        with bitmap.to_pil() as picture:
                            target = Path(directory) / "page.png"
                            picture.save(target)
                        text = self.image(target)
                        if not text.strip():
                            raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR)
                        parts.append(text)
                    finally:
                        bitmap.close()
                if len("\n".join(parts)) > 4000:
                    raise ServiceError(ErrorCode.INVALID_REQUEST)
        return "\n".join(parts)


def extract(path, creds):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return OCRClient(creds).pdf(path), "pdf_ocr"
    if suffix in {".png", ".jpg"}:
        text = OCRClient(creds).image(path)
        if text.strip():
            return text, "image_ocr"
        # Image interpretation is explicitly labelled as inference, not verified OCR.
        result = analyze(path, {"question": "Extract the contract text. Mark unreadable text explicitly.",
                                "domain": "imagev3", "temperature": 0.1, "max_tokens": 4096}, creds)
        return result["text"], "image_understanding_inference"
    if suffix == ".docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        parts = []
        for block in Document(path).iter_inner_content():
            if isinstance(block, Paragraph):
                parts.append(block.text)
            elif isinstance(block, Table):
                parts.extend(" | ".join(cell.text for cell in row.cells) for row in block.rows)
        return "\n".join(parts), "docx_extract"
    return path.read_text(encoding="utf-8-sig"), "direct_extract"


def review(payload):
    creds, store = credentials("IFLY_CONTRACT"), artifact_store()
    # Original processors use sibling imports. This path exists only in the isolated worker.
    sys.path.insert(0, str(SKILLS_ROOT / "iflytek-contract-intelligence-review" / "scripts"))
    from processors.text_cleaner import TextCleaner
    from processors.clause_splitter import ClauseSplitter
    from processors.risk_detector import RiskDetector
    from processors.compliance_checker import ComplianceChecker
    from processors.bilingual_checker import BilingualChecker
    from processors.report_builder import ReportBuilder

    with input_file(payload["file_url"], "contract", max_bytes=20 * 1024 * 1024) as source:
        text, method = extract(source.path, creds)
        suffix = source.path.suffix.lower()
    if not text.strip() or len(text) > 4000:
        raise ServiceError(ErrorCode.INVALID_REQUEST)
    text = TextCleaner().clean(text)
    clauses = ClauseSplitter().split(text)
    detector = RiskDetector()
    risks = detector.detect(clauses, payload["focus"], payload["review_mode"])
    config = SimpleNamespace(app_id=creds[0], api_key=creds[1], api_secret=creds[2],
                             timeout=45, max_input_chars=4000, require_credentials=lambda: None)
    model = LLMReviewClient(config).review_contract(text, payload["review_mode"], payload["focus"])
    translated = None
    if payload["need_translation"] or payload["lang"] == "en" or payload["review_mode"] == "deep":
        # Translation is necessary when requested; errors propagate to a failed job.
        translated = translate({"text": model.summary, "from_lang": "cn", "to_lang": "en"}, creds)["dst"]
    result = {
        "document_meta": {"filename": "contract" + suffix,
                          "input_type": "pdf" if suffix == ".pdf" else "image" if suffix in {".png", ".jpg"} else "word" if suffix == ".docx" else "text",
                          "language": payload["lang"], "review_mode": payload["review_mode"],
                          "extraction_method": method, "focus": payload["focus"] or ["all"]},
        "extraction_quality": {"text_length": len(text), "confidence": None,
                               "uncertain_regions": detector.get_uncertain_regions()},
        "clauses": clauses, "risks": risks + model.risks,
        "compliance_issues": ComplianceChecker().check(clauses),
        "bilingual_issues": BilingualChecker().check(clauses) if payload["lang"] == "bilingual" else [],
        "translation_summary": translated,
        "model_review": {"summary": model.summary, "key_clauses": model.key_clauses,
                         "suggestions": model.suggestions, "uncertain_items": model.uncertain_items,
                         "source": "model_inference"},
        "check_methods": {"compliance": "local_rules", "bilingual": "local_rules"},
        "uncertain_items": detector.get_uncertain_items(),
        "human_review_required": detector.get_human_review_flags() + ["Verify findings and model inferences against the original contract and applicable law."],
        "final_summary": model.summary,
    }
    reports = []
    if payload["output_format"] in {"json", "both"}:
        reports.append(asdict(store.put_bytes(json.dumps(result, ensure_ascii=False, indent=2).encode(), "application/json")))
    if payload["output_format"] in {"markdown", "both"}:
        # The original formatter expects a numeric confidence, but no measured score exists.
        class UnknownConfidence:
            def __format__(self, spec):
                return "Not measured; verify the source"
        quality = {**result["extraction_quality"], "confidence": UnknownConfidence()}
        report = ReportBuilder().build_markdown({**result, "extraction_quality": quality})
        report += "\n\n## Model review (inference)\n\n" + model.summary + "\n\n" + "\n".join("- " + s for s in model.suggestions)
        reports.append(asdict(store.put_bytes(report.encode(), "text/markdown")))
    return {"review": result, "reports": reports}
