from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.file_validation import detect_file_type
from app.services.text_extraction import extract_document_text, extract_text_from_image, extract_text_from_pdf, TextExtractionError, NoTextFoundError


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

CONTENT_TYPES_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


# defines the structure of a successful upload response
class UploadResponse(BaseModel): 
    document_id: str
    status: str
    original_filename: str
    stored_filename: str
    content_type: str
    file_size_bytes: int

class TextExtractionResponse(BaseModel):
    document_id: str
    status: str
    text: str
    character_count: int


@app.get("/health")
async def health_check() -> dict[str, str | int]:
    return {
        "status": "available",
        "code": 200
    }


@app.post(
    "/documents/upload",
    response_model=UploadResponse,
    status_code=201,
)
async def upload_document(
    file: Annotated[
        UploadFile,
        File(description="PDF, JPEG or PNG credit application document"),
    ],
) -> UploadResponse:
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
            detail=( "The declared file type does not match " "the actual file content." ) 
        )

    document_id = str(uuid4())
    
    stored_filename = f"{document_id}{detected_type.extension}"
    destination = UPLOAD_DIRECTORY / stored_filename

    try:
        destination.write_bytes(content)
    except OSError as error:
        raise HTTPException(
            status_code=500,
            detail="The document could not be stored.",
        ) from error
    finally:
        await file.close()

    return UploadResponse(
        document_id=document_id,
        status="uploaded",
        original_filename=file.filename or "unknown",
        stored_filename=stored_filename,
        content_type=detected_type.content_type,
        file_size_bytes=len(content),
    )


@app.post(
    "/documents/{document_id}/extract",
    response_model=TextExtractionResponse,
)
async def extract_document(
    document_id: str,
) -> TextExtractionResponse:
    matches = list(UPLOAD_DIRECTORY.glob(f"{document_id}.*"))

    if not matches:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if len(matches) > 1:
        raise HTTPException(
            status_code=500,
            detail="Multiple stored documents use this document ID.",
        )

    file_path = matches[0]
    content_type = CONTENT_TYPES_BY_EXTENSION.get(
        file_path.suffix.lower()
    )

    if content_type is None:
        raise HTTPException(
            status_code=415,
            detail="The stored document type is not supported.",
        )

    try:
        text = extract_document_text(
            file_path=file_path,
            content_type=content_type,
        )
    except NoTextFoundError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except TextExtractionError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    return TextExtractionResponse(
        document_id=document_id,
        status="extracted",
        text=text,
        character_count=len(text),
    )