from pathlib import Path

import os
import pymupdf
import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, UnidentifiedImageError
from typing import Literal
from pydantic import BaseModel

OCR_ENGINE = PaddleOCR(
    lang="de",
    device="cpu",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

class TextExtractionError(Exception):
    """Raised when text cannot be extracted from a document."""


class NoTextFoundError(TextExtractionError):
    """Raised when extraction succeeds but no usable text is found."""

class ExtractionResult(BaseModel):
    text: str
    method: Literal["embedded_text", "ocr", "hybrid"]
    page_count: int

def _ocr_image(image: Image.Image) -> str:
    image_array = np.array(
        image.convert("RGB")
    )

    try:
        results = OCR_ENGINE.predict(image_array)

    except Exception as error:
        raise TextExtractionError(
            "PaddleOCR could not process the image."
        ) from error

    detected_lines: list[str] = []

    for result in results:
        result_data = result.json["res"]

        recognized_texts = result_data.get(
            "rec_texts",
            [],
        )

        for text in recognized_texts:
            cleaned_text = text.strip()

            if cleaned_text:
                detected_lines.append(cleaned_text)

    return "\n".join(detected_lines).strip()


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
                    sort=True
                ).strip()

                if text:
                    used_embedded_text = True
                else:
                    text = _ocr_pdf_page(page)

                    if text:
                        used_ocr = True
                
                if text: 
                    page_texts.append(
                        f"--- Page {page_number} ---\n{text}"
                    )
    
    except pymupdf.FileDataError as error:
        raise TextExtractionError(
            "The PDF is invalid or corrupted"
        ) from error
    except Exception as error:
        raise TextExtractionError(
            "PaddleOCR could not process the document."
        ) from error
    except (RuntimeError, OSError) as error:
        raise TextExtractionError(
            "The PDF could not be opened or processed."
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
    except Exception as error:
        raise TextExtractionError(
            "PaddleOCR could not process the document."
        ) from error
    except OSError as error:
        raise TextExtractionError(
            "The image could not be read."
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