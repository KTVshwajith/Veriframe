import io
import random

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import Settings
from app.main import create_app
from app.storage import SQLiteRepository


def make_scene(seed: int, size=(640, 480)) -> Image.Image:
    """Deterministic synthetic 'photo': gradient background plus random shapes."""
    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    px = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            px[x, y] = (x * 255 // size[0], y * 255 // size[1], (x + y + seed * 40) % 256)
    draw = ImageDraw.Draw(img)
    for _ in range(25):
        x0, y0 = rnd.randint(0, size[0] - 60), rnd.randint(0, size[1] - 60)
        x1, y1 = x0 + rnd.randint(20, 160), y0 + rnd.randint(20, 160)
        colour = tuple(rnd.randint(0, 255) for _ in range(3))
        (draw.ellipse if rnd.random() > 0.5 else draw.rectangle)((x0, y0, x1, y1), fill=colour)
    return img


def to_bytes(img: Image.Image, fmt="PNG", **kw) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


@pytest.fixture
def original() -> Image.Image:
    return make_scene(1)


@pytest.fixture
def client():
    app = create_app(Settings(storage_backend="sqlite"), repo=SQLiteRepository(":memory:"))
    return TestClient(app)
