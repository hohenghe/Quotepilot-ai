"""Real native integration check when QP_TEST_NATIVE_IMAGE_LIBRARY is set."""
import io
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.core.config import settings
from app.services import vision


def test_cpp_library_orients_and_bounds_large_jpeg():
    library_path = os.environ.get("QP_TEST_NATIVE_IMAGE_LIBRARY", "")
    if not library_path:
        pytest.skip("C++ image library not built for this environment")
    assert Path(library_path).is_file()

    # Python >=3.8 ignores PATH for dependent DLL resolution on Windows.
    dll_dir = os.environ.get("QP_TEST_NATIVE_DLL_DIR")
    handle = os.add_dll_directory(dll_dir) if os.name == "nt" and dll_dir else None
    try:
        photo = Image.new("RGB", (4000, 3000), (30, 80, 120))
        exif = photo.getexif()
        exif[0x0112] = 6
        buffer = io.BytesIO()
        photo.save(buffer, format="JPEG", exif=exif.tobytes())
        with patch.object(settings, "NATIVE_IMAGE_PREPROCESSOR_LIBRARY", library_path), \
             patch.object(settings, "NATIVE_IMAGE_PREPROCESSOR_PATH", ""), \
             patch.object(vision, "_call_native_image_library", wraps=vision._call_native_image_library) as native:
            native_output = vision._call_native_image_library(buffer.getvalue(), 1024, 90)
            assert native_output is not None and native_output.startswith(b"\xff\xd8\xff")
            output, mime, meta = vision._preprocess(buffer.getvalue(), "image/jpeg", 1024, 90)
        assert native.call_count == 2
        assert output == native_output
        assert mime == "image/jpeg" and meta["was_resized"]
        with Image.open(io.BytesIO(output)) as processed:
            assert processed.size == (768, 1024)
            assert processed.getexif().get(0x0112) in (None, 1)
            processed.verify()
    finally:
        if handle is not None:
            handle.close()


@pytest.mark.parametrize("orientation", range(1, 9))
def test_cpp_library_matches_pillow_exif_orientation(orientation):
    library_path = os.environ.get("QP_TEST_NATIVE_IMAGE_LIBRARY", "")
    if not library_path:
        pytest.skip("C++ image library not built for this environment")
    dll_dir = os.environ.get("QP_TEST_NATIVE_DLL_DIR")
    handle = os.add_dll_directory(dll_dir) if os.name == "nt" and dll_dir else None
    try:
        photo = Image.new("RGB", (1200, 800))
        draw = ImageDraw.Draw(photo)
        colors = ((240, 20, 20), (20, 240, 20), (20, 20, 240), (240, 240, 20))
        for box, color in zip(
            ((0, 0, 599, 399), (600, 0, 1199, 399),
             (0, 400, 599, 799), (600, 400, 1199, 799)), colors,
        ):
            draw.rectangle(box, fill=color)
        exif = photo.getexif()
        exif[0x0112] = orientation
        buffer = io.BytesIO()
        photo.save(buffer, format="JPEG", quality=95, exif=exif.tobytes())
        with patch.object(settings, "NATIVE_IMAGE_PREPROCESSOR_LIBRARY", library_path), \
             patch.object(settings, "NATIVE_IMAGE_PREPROCESSOR_PATH", ""):
            native_bytes, _, _ = vision._preprocess(buffer.getvalue(), "image/jpeg", 512, 90)
        with patch.object(settings, "NATIVE_IMAGE_PREPROCESSOR_LIBRARY", ""), \
             patch.object(settings, "NATIVE_IMAGE_PREPROCESSOR_PATH", ""):
            pillow_bytes, _, _ = vision._preprocess(buffer.getvalue(), "image/jpeg", 512, 90)
        with Image.open(io.BytesIO(native_bytes)) as native, Image.open(io.BytesIO(pillow_bytes)) as pillow:
            assert native.size == pillow.size
            for x, y in ((20, 20), (native.width - 20, 20),
                         (20, native.height - 20), (native.width - 20, native.height - 20)):
                assert all(abs(a - b) <= 20 for a, b in zip(native.getpixel((x, y)), pillow.getpixel((x, y))))
    finally:
        if handle is not None:
            handle.close()
