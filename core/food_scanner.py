from __future__ import annotations

from os import PathLike
from typing import IO, Optional, Union

from PIL import Image
from pyzbar.pyzbar import decode as decode_barcode

ImageSource = Union[str, bytes, PathLike[str], PathLike[bytes], IO[bytes]]


class FoodScanner:
    """Decode barcodes from an image."""

    @staticmethod
    def decode(image_file: ImageSource) -> Optional[str]:
        try:
            img = Image.open(image_file)
            codes = decode_barcode(img)
            return codes[0].data.decode("utf-8") if codes else None
        except Exception:
            return None
