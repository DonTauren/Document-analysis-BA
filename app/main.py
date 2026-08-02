from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from time import perf_counter

from app.services.file_validation import detect_file_type
from app.services.text_extraction import extract_document_text, TextExtractionError, NoTextFoundError
from app.services.field_extraction import CreditApplicationFields, FieldExtractionError, extract_credit_application_fields


app = FastAPI(
    title="Credit Document Verification API",
    description="Prototype API for uploading credit application documents.",
    version="0.1.0",
)


UPLOAD_DIRECTORY = Path("uploads")
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

class DocumentProcessingResponse(BaseModel):
    document_id: str
    extraction_method: Literal[
        "embedded_text",
        "ocr",
        "hybrid"
    ]
    page_count: int
    processing_time_seconds: float
    fields: CreditApplicationFields
    # debugging purposes
    raw_text: str


@app.get("/health")
async def health_check() -> dict[str, str | int]:
    return {
        "status": "available",
        "code": 200
    }


@app.post(
    "/documents/process",
    response_model=DocumentProcessingResponse,
    status_code=200,
)
async def process_document(
    file: Annotated[
        UploadFile,
        File(description="PDF, JPEG or PNG credit application document"),
    ],
) -> DocumentProcessingResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        await file.close()

        raise HTTPException(
            status_code=415,
            detail="Only PDF, JPEG and PNG files are accepted.",
        )

    content = await file.read(MAX_FILE_SIZE_BYTES + 1)

    if not content:
        await file.close()

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        await file.close()

        raise HTTPException(
            status_code=413,
            detail="The uploaded file exceeds the 10 MB limit.",
        )
    
    detected_type = detect_file_type(content)

    if detected_type is None:
        await file.close()

        raise HTTPException(
            status_code=415, 
            detail=("The upload content is not a supported PDF, JPG or PNG file.")
        )
    
    if detected_type.content_type != file.content_type: 
        await file.close()

        raise HTTPException( 
            status_code=415, 
            detail=("The declared file type does not match the actual file content.") 
        )

    document_id = str(uuid4())
    stored_filename = f"{document_id}{detected_type.extension}"
    destination = UPLOAD_DIRECTORY / stored_filename

    try:
        start_total = perf_counter()
        save_start = perf_counter()

        await run_in_threadpool(
            destination.write_bytes,
            content
        )

        save_duration = perf_counter() - save_start
        extraction_start = perf_counter()

        text_result = await run_in_threadpool(
            extract_document_text,
            destination, 
            detected_type.content_type
        )

        fields = await run_in_threadpool(
            extract_credit_application_fields,
            text_result.text
        )

        extraction_duration = (perf_counter() - extraction_start)
        total_duration = (perf_counter() - start_total)

        print(f"Save duration: {save_duration:.2f} seconds")
        print(f"Extraction duration: {extraction_duration:.2f} seconds")
        print(f"Total duration: {total_duration:.2f} seconds")

    except NoTextFoundError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        ) from error
    except FieldExtractionError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except TextExtractionError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        ) from error
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail="The document could not be stored.",
        ) from error
    
    finally:
        await file.close()

    return DocumentProcessingResponse(
        document_id=document_id,
        extraction_method=text_result.method,
        page_count=text_result.page_count,
        processing_time_seconds=round(total_duration, 3),
        fields=fields,
        raw_text=text_result.text
    )