"""Bounded image decoding and metadata-free, mobile-sized JPEG output."""
from dataclasses import dataclass
from io import BytesIO
from threading import BoundedSemaphore
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PHOTOS = 4
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_STORED_BYTES = 768 * 1024
MIN_DIMENSION = 200
MAX_DIMENSION = 1200
ALLOWED_FORMATS = ('JPEG', 'PNG', 'WEBP')
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
_DECODE_SLOTS = BoundedSemaphore(2)


class PhotoError(ValueError):
    pass


@dataclass(frozen=True)
class ProcessedPhoto:
    data: bytes
    width: int
    height: int


def process_photo(content: bytes) -> ProcessedPhoto:
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise PhotoError('Choose an image no larger than 8 MB.')
    # Bound concurrent decoded-image memory even when many authenticated
    # requests reach the thread pool together.
    with _DECODE_SLOTS:
        return _decode_photo(content)


def _decode_photo(content: bytes) -> ProcessedPhoto:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            # Restrict decoders before inspection; filenames and MIME labels
            # never determine whether the upload is actually a supported image.
            with Image.open(BytesIO(content), formats=ALLOWED_FORMATS) as probe:
                if getattr(probe, 'is_animated', False):
                    raise PhotoError('Choose a still JPEG, PNG, or WebP image, rather than an animation.')
                width, height = probe.size
                if min(width, height) < MIN_DIMENSION:
                    raise PhotoError('Choose a photo at least 200 × 200 pixels.')
                if width * height > MAX_PIXELS or max(width, height) > 10_000:
                    raise PhotoError('Choose a photo with at most 20 megapixels and 10,000 pixels per side.')
                probe.verify()
            with Image.open(BytesIO(content), formats=ALLOWED_FORMATS) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
                rgba = oriented.convert('RGBA')
                # New pixels on a clean canvas: no EXIF, GPS, comments, XMP,
                # filename or colour-profile metadata is carried into storage.
                clean = Image.new('RGB', rgba.size, 'white')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                for quality in (82, 74, 66, 58):
                    result = BytesIO()
                    clean.save(result, 'JPEG', quality=quality, optimize=True,
                               progressive=True, exif=b'', icc_profile=None)
                    data = result.getvalue()
                    if len(data) <= MAX_STORED_BYTES:
                        return ProcessedPhoto(data, *clean.size)
                raise PhotoError('This photo could not be compressed enough. Choose a smaller image.')
    except PhotoError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise PhotoError('Choose a photo with at most 20 megapixels.') from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise PhotoError('This file is not a valid still JPEG, PNG, or WebP image.') from None
