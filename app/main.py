from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel


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


# defines the structure of a successful upload response
class UploadResponse(BaseModel): 
    document_id: str
    status: str
    original_filename: str
    stored_filename: str
    content_type: str
    file_size_bytes: int


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

    document_id = str(uuid4())
    extension = ALLOWED_CONTENT_TYPES[file.content_type]
    stored_filename = f"{document_id}{extension}"
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
        content_type=file.content_type,
        file_size_bytes=len(content),
    )