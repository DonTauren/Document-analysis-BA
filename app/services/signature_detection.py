from pathlib import Path

import cv2
import numpy as np
import pymupdf


# Bereich auf der letzten Seite:
# links, oben, rechts, unten
# Werte liegen zwischen 0.0 und 1.0.
SIGNATURE_REGION = (
    0.13,
    0.812,
    0.40,
    0.87,
)


def has_handwritten_signature(
    pdf_path: Path,
) -> bool:
    with pymupdf.open(pdf_path) as document:
        page = document[-1]

        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(2, 2),
            alpha=False,
        )

    image = np.frombuffer(
        pixmap.samples,
        dtype=np.uint8,
    ).reshape(
        pixmap.height,
        pixmap.width,
        3,
    )

    height, width = image.shape[:2]

    left, top, right, bottom = SIGNATURE_REGION

    signature_area = image[
        int(height * top):int(height * bottom),
        int(width * left):int(width * right),
    ]

    grayscale = cv2.cvtColor(
        signature_area,
        cv2.COLOR_RGB2GRAY,
    )

    _, binary = cv2.threshold(
        grayscale,
        200,
        255,
        cv2.THRESH_BINARY_INV
    )

    ink_ratio = (
        cv2.countNonZero(binary)
        / binary.size
    )

    return ink_ratio > 0.01