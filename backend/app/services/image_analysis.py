"""Safe image intake and conservative wire-geometry hints."""

from io import BytesIO
from typing import List, Tuple
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_SIDE = 2048


def normalize_image(data: bytes) -> Tuple[bytes, int, int]:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image is empty or exceeds the 10 MB upload limit")
    try:
        image = Image.open(BytesIO(data))
        if image.format not in ("PNG", "JPEG"):
            raise ValueError("Upload a PNG or JPG schematic image")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The uploaded file is not a valid PNG or JPG image") from exc
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise ValueError("Image dimensions exceed the 20 megapixel limit")
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    width, height = image.size
    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue(), width, height


def detect_line_hints(image_bytes: bytes, width: int, height: int) -> Tuple[List[List[float]], List[str]]:
    """Return candidate horizontal/vertical segments and crossing warnings.

    These are visual hints only. They are never used to merge electrical nodes.
    """
    try:
        import cv2
        import numpy as np
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return [], []
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 35, minLineLength=24, maxLineGap=8)
        if lines is None:
            return [], []
        horizontal, vertical = [], []
        for raw in lines[:, 0, :]:
            x1, y1, x2, y2 = [int(v) for v in raw]
            dx, dy = x2 - x1, y2 - y1
            if abs(dx) >= 24 and abs(dy) <= max(3, abs(dx) * 0.035):
                horizontal.append((min(x1, x2), (y1 + y2) // 2, max(x1, x2)))
            elif abs(dy) >= 24 and abs(dx) <= max(3, abs(dy) * 0.035):
                vertical.append(((x1 + x2) // 2, min(y1, y2), max(y1, y2)))
        segments = [[x1 / width, y / height, x2 / width, y / height] for x1, y, x2 in horizontal]
        segments.extend([[x / width, y1 / height, x / width, y2 / height] for x, y1, y2 in vertical])
        segments = segments[:120]
        crossing_count = 0
        for x, y1, y2 in vertical:
            for x1, y, x2 in horizontal:
                if x1 + 3 < x < x2 - 3 and y1 + 3 < y < y2 - 3:
                    crossing_count += 1
        warnings = ([f"Image geometry found {crossing_count} possible wire crossing(s); crossing connectivity needs user confirmation."] if crossing_count else [])
        return segments, warnings
    except (ImportError, ValueError):
        return [], []
