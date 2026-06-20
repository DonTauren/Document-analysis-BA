from dataclasses import dataclass


@dataclass(frozen=True)
class DetectedFileType:
    content_type: str
    extension: str


FILE_SIGNATURES = {
    b"%PDF-": DetectedFileType("application/pdf", ".pdf"),
    b"\xff\xd8\xff": DetectedFileType("image/jpeg", ".jpg"),
    b"\x89PNG\r\n\x1a\n": DetectedFileType("image/png", ".png"),
}


def detect_file_type(file_bytes: bytes) -> DetectedFileType | None:
    for signature, file_type in FILE_SIGNATURES.items():
        if file_bytes.startswith(signature):
            return file_type

    return None