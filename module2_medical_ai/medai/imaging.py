"""Image loading, page detection, deskew, enhancement and quality checks."""
import io

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_PIXELS = 100_000_000
TARGET_MIN_SIDE = 1800  # OCR reads small print better when the page is about this size


def load_image(data: bytes) -> np.ndarray:
    """Bytes -> BGR array, honouring the phone's rotation flag (EXIF)."""
    Image.MAX_IMAGE_PIXELS = None
    img = Image.open(io.BytesIO(data))
    if img.width * img.height > MAX_PIXELS:
        raise ValueError("The image resolution is too large.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def _order_points(pts):
    pts = pts.reshape(4, 2).astype("float32")
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def find_page(img):
    """If the picture shows a sheet of paper on a darker surface (a phone photo),
    cut the sheet out and straighten its perspective. Returns None if no clear
    page outline is found."""
    h, w = img.shape[:2]
    scale = 800 / max(h, w)
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (7, 7), 0)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    best = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(best) / (small.shape[0] * small.shape[1])
    if not 0.25 < area < 0.97:  # whole frame = already a flat scan; tiny = not a page
        return None
    approx = cv2.approxPolyDP(best, 0.02 * cv2.arcLength(best, True), True)
    if len(approx) != 4 or not cv2.isContourConvex(approx):
        return None
    quad = _order_points(approx) / scale
    tl, tr, br, bl = quad
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if min(width, height) < 400:
        return None
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    return cv2.warpPerspective(img, cv2.getPerspectiveTransform(quad, dst), (width, height), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)


def estimate_skew(gray) -> float:
    """Angle (degrees) the text lines are tilted, searched between -10 and +10.
    Uses only dark text pixels (uneven lighting removed first) and returns 0
    unless a tilt clearly makes the text rows sharper than they already are."""
    f = min(1.0, 900 / max(gray.shape))
    small = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    background = cv2.medianBlur(small, 31)  # paper brightness, ignoring the text
    binary = (cv2.subtract(background, small) > 28).astype(np.uint8) * 255
    if binary.sum() < 255 * 200:  # almost no text found
        return 0.0
    h, w = binary.shape

    def sharpness(angle):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), float(angle), 1.0)
        rot = cv2.warpAffine(binary, m, (w, h), flags=cv2.INTER_NEAREST)
        return float(np.var(rot.sum(axis=1)))

    base = sharpness(0.0)
    best_angle, best_score = 0.0, base
    for angle in np.arange(-10, 10.01, 0.25):
        score = sharpness(angle)
        if score > best_score:
            best_angle, best_score = float(angle), score
    return best_angle if best_score > base * 1.08 else 0.0


def rotate(img, angle):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def quality_report(gray) -> dict:
    """Simple measurable signals about how readable the picture is."""
    h, w = gray.shape
    norm = cv2.resize(gray, (1000, max(1, int(1000 * h / w))), interpolation=cv2.INTER_AREA)
    blur = float(cv2.Laplacian(norm, cv2.CV_64F).var())
    brightness = float(gray.mean())
    background = cv2.medianBlur(norm, 31)
    contrast = float(np.percentile(cv2.subtract(background, norm), 99.5))  # how dark the text is vs the paper
    issues = []
    if blur < 120:
        issues.append("blurry")
    if brightness < 90:
        issues.append("too dark")
    elif brightness > 245:
        issues.append("overexposed")
    if contrast < 60:
        issues.append("low contrast")
    if min(h, w) < 900:
        issues.append("low resolution")
    return {"sharpness": round(blur, 1), "brightness": round(brightness, 1), "contrast": round(contrast, 1),
            "width": w, "height": h, "issues": issues}


def prepare_for_ocr(img):
    """Straighten, enhance and size a page image for OCR. Returns (gray_image, notes, quality)."""
    notes = []
    page = find_page(img)
    if page is not None:
        img = page
        notes.append("page outline detected and straightened")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    angle = estimate_skew(gray)
    if 0.4 <= abs(angle) <= 10:
        gray = rotate(gray, angle)
        notes.append(f"deskewed {angle:+.1f} degrees")
    quality = quality_report(gray)
    if min(gray.shape) < TARGET_MIN_SIDE:
        f = TARGET_MIN_SIDE / min(gray.shape)
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
        notes.append(f"enlarged x{f:.1f}")
    # No contrast boosting on purpose: in tests it turned small decimal points
    # into noise and made '9.8' read as '86'. Plain, enlarged grey reads best.
    return gray, notes, quality
