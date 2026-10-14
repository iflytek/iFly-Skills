"""Decode bounded inputs before handing them to the original Skill clients."""

from contextlib import contextmanager
from pathlib import Path
import shutil
from urllib.parse import urlsplit
from zipfile import ZipFile

from .files import FileAccessError, FileDownloader, FilePolicy


def inspect_file(path: Path, kind: str, url: str = "") -> tuple[str, str]:
    with path.open("rb") as stream:
        header = stream.read(16)
    if kind == "image" or kind == "contract" and header.startswith((b"\x89PNG", b"\xff\xd8")):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 16_000_000
        with Image.open(path) as img:
            if img.format not in {"PNG", "JPEG"} or img.width * img.height > 16_000_000:
                raise FileAccessError("Unsupported image")
            suffix, mime = (".png", "image/png") if img.format == "PNG" else (".jpg", "image/jpeg")
            img.verify()
        return suffix, mime
    if kind == "pdf" or kind == "contract" and header.startswith(b"%PDF-"):
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(path) as pdf:
            if not 1 <= len(pdf) <= (8 if kind == "contract" else 100):
                raise FileAccessError("PDF page limit exceeded")
        return ".pdf", "application/pdf"
    if kind == "mp3":
        from mutagen.mp3 import MP3
        audio = MP3(path)
        if audio.info.length <= 0:
            raise FileAccessError("Invalid MP3")
        return ".mp3", "audio/mpeg"
    if kind == "sample":
        if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
            import wave
            with wave.open(str(path)) as audio:
                if (audio.getnframes() <= 0 or audio.getnchannels() != 1 or audio.getsampwidth() != 2
                        or audio.getframerate() < 24000 or audio.getnframes() / audio.getframerate() > 40):
                    raise FileAccessError("Invalid training WAV")
            return ".wav", "audio/wav"
        from mutagen.mp3 import MP3
        audio = MP3(path)
        if not (0 < audio.info.length <= 40 and audio.info.channels == 1 and audio.info.sample_rate >= 24000):
            raise FileAccessError("Invalid training MP3")
        return inspect_file(path, "mp3")
    if kind == "video":
        if header[4:8] != b"ftyp":
            raise FileAccessError("An MP4 container is required")
        from mutagen.mp4 import MP4
        video = MP4(path)
        if video.info.length <= 0:
            raise FileAccessError("Invalid MP4")
        return ".mp4", "video/mp4"
    if kind == "contract":
        suffix = Path(urlsplit(url).path).suffix.lower()
        if suffix == ".docx" and header.startswith(b"PK"):
            with ZipFile(path) as archive:
                if (len(archive.infolist()) > 2000 or sum(i.file_size for i in archive.infolist()) > 32 * 1024 * 1024
                        or "word/document.xml" not in archive.namelist()):
                    raise FileAccessError("Invalid DOCX")
            return ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8-sig")
            if not text.strip() or "\x00" in text:
                raise FileAccessError("Invalid text document")
            return suffix, "text/plain"
    raise FileAccessError("Unsupported file format")


@contextmanager
def input_file(url: str, kind: str, *, max_bytes: int = 4 * 1024 * 1024):
    with FileDownloader(FilePolicy(max_bytes=max_bytes)).download(url) as downloaded:
        try:
            suffix, mime = inspect_file(downloaded.path, kind, url)
        except Exception:
            raise FileAccessError("The downloaded media is invalid.") from None
        target = downloaded.path.with_suffix(suffix)
        shutil.move(str(downloaded.path), str(target))
        downloaded.path = target
        downloaded.mime_type = mime
        yield downloaded
