"""Image fingerprinting.

Three layers of fingerprint are taken for every image:

* SHA-256 of the raw bytes   -> proves a file is byte-for-byte identical.
* Perceptual hash (pHash)    -> survives re-compression, resizing and format
                                changes, so we can still find the original.
* Block hash grid (4 x 4)    -> one small hash per region, so that when an image
                                *has* changed we can say *where* it changed.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import imagehash
from PIL import Image, UnidentifiedImageError

GRID = 4  # 4 x 4 = 16 regions
NORMALISED_SIZE = 256


class InvalidImageError(ValueError):
    """Raised when uploaded bytes are not a decodable image."""


@dataclass(frozen=True)
class Fingerprint:
    sha256: str
    phash: str
    block_hashes: list[str]
    width: int
    height: int
    format: str


def load_image(data: bytes) -> Image.Image:
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()  # integrity check; image must be reopened afterwards
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidImageError("File is not a valid image") from exc


def _block_hashes(img: Image.Image) -> list[str]:
    norm = img.convert("L").resize((NORMALISED_SIZE, NORMALISED_SIZE), Image.Resampling.LANCZOS)
    step = NORMALISED_SIZE // GRID
    hashes = []
    for row in range(GRID):
        for col in range(GRID):
            box = (col * step, row * step, (col + 1) * step, (row + 1) * step)
            hashes.append(str(imagehash.phash(norm.crop(box), hash_size=8)))
    return hashes


def fingerprint(data: bytes) -> Fingerprint:
    img = load_image(data)
    return Fingerprint(
        sha256=hashlib.sha256(data).hexdigest(),
        phash=str(imagehash.phash(img.convert("RGB"))),
        block_hashes=_block_hashes(img),
        width=img.width,
        height=img.height,
        format=(img.format or "unknown").upper(),
    )


def hamming(a: str, b: str) -> int:
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def changed_regions(original: list[str], candidate: list[str], threshold: int) -> list[dict]:
    """Return the grid cells whose hash distance exceeds the threshold."""
    regions = []
    for i, (a, b) in enumerate(zip(original, candidate, strict=True)):
        distance = hamming(a, b)
        if distance > threshold:
            regions.append({"row": i // GRID, "col": i % GRID, "distance": distance})
    return regions
