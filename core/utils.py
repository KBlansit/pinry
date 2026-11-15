import hashlib
import os

import PIL.Image

# Map Pillow formats to a safe file extension. Uploaded files are always
# renamed with the extension of their *detected* format so a crafted file
# (e.g. "evil.png.html") can never be served with a non-image content type.
_FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "MPO": ".jpg",
    "PNG": ".png",
    "GIF": ".gif",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "ICO": ".ico",
}


def detect_image_extension(file_obj):
    """Return a safe extension for an image file object, or "" if unknown."""
    try:
        pos = file_obj.tell()
    except (AttributeError, OSError, ValueError):
        pos = None
    try:
        file_obj.seek(0)
        with PIL.Image.open(file_obj) as im:
            fmt = im.format
    except Exception:
        fmt = None
    finally:
        try:
            file_obj.seek(pos or 0)
        except (AttributeError, OSError, ValueError):
            pass
    return _FORMAT_EXTENSIONS.get(fmt, "")


def upload_path(instance, filename, **kwargs):
    hasher = hashlib.md5()
    for chunk in instance.image.chunks():
        hasher.update(chunk)
    hash = hasher.hexdigest()
    base, _ = os.path.splitext(os.path.basename(filename))
    base = base[:100] or "image"
    ext = detect_image_extension(instance.image) or ".img"
    return '%(first)s/%(second)s/%(hash)s/%(base)s%(ext)s' % {
        'first': hash[0],
        'second': hash[1],
        'hash': hash,
        'base': base,
        'ext': ext,
    }
