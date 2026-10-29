import io
import os
import re
import secrets
import threading

from PIL import Image

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}
FORMAT_TO_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
EXT_TO_MIME = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
MAX_PIXELS = 100_000_000  # large enough for 48 MP phone cameras

_pil_lock = threading.Lock()


class DocumentError(ValueError):
    pass


def safe_display_name(name):
    """Keep only the file's base name, strip odd characters, cap the length."""
    base = os.path.basename((name or "").replace("\\", "/")) or "document"
    base = re.sub(r"[^\w.\- ()]", "_", base)
    return base[:200]


def _check_image(data):
    # Pillow's own size guard is global, so relax it only while we check the
    # pixel count ourselves.
    with _pil_lock:
        previous = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            probe = Image.open(io.BytesIO(data))
            fmt = probe.format
            width, height = probe.size
            if fmt not in FORMAT_TO_EXT:
                raise DocumentError("Images must be JPG, PNG or WEBP.")
            if width * height > MAX_PIXELS:
                raise DocumentError("The image resolution is too large.")
            probe.verify()
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("The file is not a valid image.")
        finally:
            Image.MAX_IMAGE_PIXELS = previous
    return FORMAT_TO_EXT[fmt]


def validate_document(file_storage, max_bytes):
    """Check the extension, size and REAL content type. Returns
    (bytes, extension, mime). The original bytes are kept unchanged because
    OCR works best on the untouched file."""
    name = (file_storage.filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentError("Upload a PDF, JPG, PNG or WEBP file.")

    data = file_storage.read(max_bytes + 1)
    if not data:
        raise DocumentError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise DocumentError(f"File must be smaller than {max_bytes // (1024 * 1024)} MB.")

    if ext == "pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentError("The file is not a valid PDF.")
        real_ext = "pdf"
    else:
        real_ext = _check_image(data)  # trusts the content, not the file name
    return data, real_ext, EXT_TO_MIME[real_ext]


def save_document(upload_folder, patient_id, data, ext):
    rel = os.path.join("documents", f"patient_{patient_id}", f"{secrets.token_hex(12)}.{ext}")
    full = os.path.join(upload_folder, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(data)
    return rel


def delete_document_file(upload_folder, rel_path):
    if not rel_path:
        return
    full = os.path.abspath(os.path.join(upload_folder, rel_path))
    root = os.path.abspath(upload_folder)
    if full.startswith(root + os.sep) and os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass  # file briefly locked on Windows; the database row is already gone
