from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, UnidentifiedImageError

class TextExtractionError(Exception):
    """Raised when text cannot be extracted from a document."""


class NoTextFoundError(TextExtractionError):
    """Raised when extraction succeeds but no usable text is found."""

def extract_text_from_pdf(file_path: Path) -> str:
    try:
        with pymupdf.open(file_path) as document:
            pages = [
                page.get_text("text", sort=True).strip()
                for page in document
            ]
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise TextExtractionError(
            "The PDF could not be opened or processed."
        ) from error

    text = "\n\n".join(page for page in pages if page).strip()

    if not text:
        raise NoTextFoundError(
            "No embedded text was found in the PDF."
        )

    return text


def extract_text_from_image(file_path: Path) -> str:
    try:
        with Image.open(file_path) as image:
            image.load()

            text = pytesseract.image_to_string(
                image,
                lang="eng",
            ).strip()

    except UnidentifiedImageError as error:
        raise TextExtractionError(
            "The image could not be opened."
        ) from error
    except pytesseract.TesseractNotFoundError as error:
        raise TextExtractionError(
            "Tesseract OCR is not installed or cannot be found."
        ) from error
    except pytesseract.TesseractError as error:
        raise TextExtractionError(
            "Tesseract OCR could not process the image."
        ) from error
    except OSError as error:
        raise TextExtractionError(
            "The image could not be read."
        ) from error

    if not text:
        raise NoTextFoundError(
            "No text was detected in the image."
        )

    return text


def extract_document_text(
    file_path: Path,
    content_type: str,
) -> str:
    if content_type == "application/pdf":
        return extract_text_from_pdf(file_path)

    if content_type in {"image/jpeg", "image/png"}:
        return extract_text_from_image(file_path)

    raise TextExtractionError(
        f"Unsupported content type: {content_type}"
    )