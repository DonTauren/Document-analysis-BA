from __future__ import annotations
from pathlib import Path
import logging
from threading import Lock

import pymupdf
import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, UnidentifiedImageError
from typing import Any, Literal
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OCR_ENGINE = PaddleOCR(
    lang="de",
    device="cpu",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False
)

OCR_Lock = Lock()

class TextExtractionError(Exception):
    """Raised when text cannot be extracted from a document."""


class NoTextFoundError(TextExtractionError):
    """Raised when extraction succeeds but no usable text is found."""

class ExtractionResult(BaseModel):
    text: str
    method: Literal["embedded_text", "ocr", "hybrid"]
    page_count: int

def _extract_texts_from_result(result: Any) -> list[str]:

    result_data = getattr(result, "json", None)

    # Some libraries expose json as a method rather than a property.
    if callable(result_data):
        result_data = result_data()

    if not isinstance(result_data, dict):
        raise TypeError(
            "PaddleOCR returned an unexpected result format."
        )

    # Support both nested and non-nested result dictionaries.
    payload = result_data.get("res", result_data)

    if not isinstance(payload, dict):
        raise TypeError(
            "PaddleOCR result payload is not a dictionary."
        )

    recognized_texts = payload.get("rec_texts", [])

    if recognized_texts is None:
        return []

    if isinstance(recognized_texts, str):
        recognized_texts = [recognized_texts]

    detected_lines: list[str] = []

    for text in recognized_texts:
        cleaned_text = str(text).strip()

        if cleaned_text:
            detected_lines.append(cleaned_text)

    return detected_lines

def _ocr_image(image: Image.Image) -> str:

    try:
        image_array = np.ascontiguousarray(
            np.array(
                image.convert("RGB"),
                dtype=np.uint8
            )
        )

        with OCR_Lock:
            results = list(
                OCR_ENGINE.predict(image_array)
            )

        detected_lines: list[str] = []

        for result in results: 
            detected_lines.extend(
                _extract_texts_from_result(result)
            )

        return "\n".join(detected_lines).strip()

    except Exception as error:
        logger.exception("PaddleOCR failed while processing an image") 
        raise TextExtractionError("PaddleOCR could not process the image") from error


def _ocr_pdf_page(page: pymupdf.Page) -> str:
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(2, 2),
        alpha=False,
    )

    image = Image.frombytes(
        "RGB",
        (pixmap.width, pixmap.height),
        pixmap.samples,
    )

    try:
        return _ocr_image(image)
    finally:
        image.close()

def extract_text_from_pdf(file_path: Path) -> ExtractionResult:
    page_texts: list[str] = []

    used_embedded_text = False
    used_ocr = False

    try: 
        with pymupdf.open(file_path) as document:
            page_count = len(document)

            for page_number, page in enumerate(document, start=1): 
                text = page.get_text(
                    "text", 
                    sort = True
                ).strip()

                if text:
                    used_embedded_text = True
                else:
                    used_ocr = True
                    text = _ocr_pdf_page(page)
                
                if text: 
                    page_texts.append(
                        f"--- Page {page_number} ---\n{text}"
                    )
                else:
                    logger.warning("No text was found on PDF page %s.", page_number)

    except TextExtractionError:
        raise
    
    except pymupdf.FileDataError as error:
        raise TextExtractionError(
            "The PDF is invalid or corrupted"
        ) from error
    except (RuntimeError, OSError) as error:
        logger.exception("PymuPDF could not process the PDF")
        raise TextExtractionError(
            "The PDF could not be opened or processed."
        ) from error
    except Exception as error:
        logger.exception("An unexpected PDF extraction error occured")
        raise TextExtractionError(
            "PaddleOCR could not process the document."
        ) from error
    
    text = "\n\n".join(page_texts).strip()

    if not text:
        raise NoTextFoundError(
            "No text could be extracted from the PDF."
        )
    
    if used_embedded_text and used_ocr:
        method: Literal[
            "embedded_text",
            "ocr",
            "hybrid"
        ] = "hybrid"
    elif used_ocr: 
        method = "ocr"
    else: 
        method = "embedded_text"

    return ExtractionResult(
        text=text, 
        method=method,
        page_count=page_count
    )

def extract_text_from_image(file_path: Path) -> ExtractionResult:
    try:
        with Image.open(file_path) as image:
            image.load()

            text = _ocr_image(image)

    except UnidentifiedImageError as error:
        raise TextExtractionError(
            "The image could not be opened."
        ) from error
    except TextExtractionError:
        raise
    except OSError as error:
        logger.exception("The uploaded image could not be read")
        raise TextExtractionError(
            "The image could not be read."
        ) from error
    except Exception as error:
        logger.exception("An unexpected image extraction error occurred.")
        raise TextExtractionError(
            "An unexpected image extraction error occurred."
        ) from error

    if not text:
        raise NoTextFoundError(
            "No text was detected in the image."
        )

    return ExtractionResult(
        text=text,
        method="ocr",
        page_count=1
    )


def extract_document_text(
    file_path: Path,
    content_type: str,
) -> ExtractionResult:
    if content_type == "application/pdf":
        return extract_text_from_pdf(file_path)

    if content_type in {"image/jpeg", "image/png"}:
        return extract_text_from_image(file_path)

    raise TextExtractionError(
        f"Unsupported content type: {content_type}"
    )