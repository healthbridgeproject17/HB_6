import io
import os
import secrets

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 25_000_000  # refuse decompression bombs

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class PhotoError(ValueError):
    pass


def process_photo(file_storage, max_bytes):
    """Validate an uploaded profile photo and return clean JPEG bytes.

    Checks extension, size, and that the content is a REAL image (not just a
    renamed file). The image is re-encoded, which strips metadata such as GPS."""
    name = (file_storage.filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise PhotoError("Photo must be a JPG, PNG or WEBP image.")

    data = file_storage.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise PhotoError(f"Photo must be smaller than {max_bytes // (1024 * 1024)} MB.")
    if not data:
        raise PhotoError("The uploaded file is empty.")

    try:
        probe = Image.open(io.BytesIO(data))
        if probe.format not in ALLOWED_FORMATS:
            raise PhotoError("Photo must be a JPG, PNG or WEBP image.")
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except PhotoError:
        raise
    except Exception:
        raise PhotoError("The file is not a valid image.")

    img.thumbnail((512, 512))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()


def save_photo(upload_folder, patient_id, jpeg_bytes):
    """Write the photo and return its path relative to the upload folder."""
    photos_dir = os.path.join(upload_folder, "photos")
    os.makedirs(photos_dir, exist_ok=True)
    rel = os.path.join("photos", f"patient_{patient_id}_{secrets.token_hex(8)}.jpg")
    with open(os.path.join(upload_folder, rel), "wb") as fh:
        fh.write(jpeg_bytes)
    return rel


def delete_photo(upload_folder, rel_path):
    if not rel_path:
        return
    full = os.path.abspath(os.path.join(upload_folder, rel_path))
    root = os.path.abspath(upload_folder)
    if full.startswith(root + os.sep) and os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            # Windows can briefly lock a file that is being read. The database
            # no longer points at it, so a leftover file is harmless; skip it.
            pass
