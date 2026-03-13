from PIL import Image
from pyzbar.pyzbar import decode as decode_barcode


class FoodScanner:
    """Decode barcodes from an image."""

    @staticmethod
    def decode(image_file):
        try:
            img = Image.open(image_file)
            codes = decode_barcode(img)
            return codes[0].data.decode("utf-8") if codes else None
        except Exception:
            return None
