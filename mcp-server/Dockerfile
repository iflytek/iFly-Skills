FROM python:3.13-slim

WORKDIR /app

COPY skills/iflytek-hyper-tts ./skills/iflytek-hyper-tts
COPY skills/iflytek-image-understanding ./skills/iflytek-image-understanding
COPY skills/iflytek-ocr-invoice ./skills/iflytek-ocr-invoice
COPY skills/iflytek-pdf-image-ocr ./skills/iflytek-pdf-image-ocr
COPY skills/iflytek-speed-transcription ./skills/iflytek-speed-transcription
COPY skills/iflytek-text-proofread ./skills/iflytek-text-proofread
COPY skills/iflytek-translate ./skills/iflytek-translate
COPY mcp-server/pyproject.toml mcp-server/README.md ./mcp-server/
COPY mcp-server/iflyskills_mcp ./mcp-server/iflyskills_mcp

RUN pip install --no-cache-dir ./mcp-server \
    && useradd --create-home --uid 10001 iflyskills

ENV IFLY_SKILLS_ROOT=/app \
    PYTHONUNBUFFERED=1

USER iflyskills

ENTRYPOINT ["iflyskills-mcp"]
