from collections.abc import Sequence

from wand.font import Font
from wand.image import Image


def generate_label_image(contents: Sequence[str], filename: str) -> None:
    with Image() as img:
        img.background_color = 'white'
        img.font = Font('Noto', 20)
        img.read(filename='label: Your Curved Text  Your Curved Text ')
        img.virtual_pixel = 'white'
        # 360 degree arc, rotated -90 degrees
        img.distort('arc', (360, -90))
        img.format = 'png'
        img.save(filename='arc_text.png')
