import io

from app.config import settings


class ExtractionError(ValueError):
    pass


def extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("This PDF is password protected.")
        if len(reader.pages) > settings.max_pdf_pages:
            raise ExtractionError(f"This PDF has more than {settings.max_pdf_pages} pages.")
        pages = [(p.extract_text() or "").strip() for p in reader.pages]
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError("This file could not be read as a PDF.") from e
    text = "\n\n".join(p for p in pages if p)
    if not text:
        raise ExtractionError("No selectable text found. Scanned PDFs need OCR, which isn't supported.")
    return text
