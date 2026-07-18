"""Generate SYNTHETIC image-only threat samples for testing vision extraction.

These bake the "message" INTO the image so the enrichment agent's vision must OCR the text /
read the scene (no caption). They are deliberately NON-GRAPHIC — text on a card, and a crude
overlay of a kitchen-knife photo above a generic stock person — used only to test that the
pipeline can extract a name, spot a weapon, and attribute a threat to a protected entity.

  threat_kill_note.png    -> a card reading a NAME + the word "KILL" (OCR test)
  person_knife_named.png  -> generic person + overlaid knife + a NAME label (link test)

Run:  python data/seed/make_threat_images.py
Output: data/images/*.png   (gitignored)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DATA_DIR = Path(__file__).resolve().parent.parent  # backend/data
IMAGES_DIR = DATA_DIR / "images"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arialbd.ttf", "Arial_Bold.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _centered(draw: ImageDraw.ImageDraw, y: int, text: str, fnt, fill, width: int) -> None:
    tb = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((width - (tb[2] - tb[0])) / 2, y), text, font=fnt, fill=fill)


def make_kill_note(dest: Path, name: str) -> None:
    """A dark 'threat card' with the target's name and the word KILL (for OCR)."""
    w, h = 680, 440
    img = Image.new("RGB", (w, h), (14, 14, 18))
    d = ImageDraw.Draw(img)
    _centered(d, 40, "KILL", font(150), (200, 30, 30), w)
    _centered(d, 215, name.upper(), font(60), (240, 240, 240), w)
    _centered(d, 315, "you can't hide", font(34), (170, 170, 170), w)
    img.save(dest)


def make_person_knife(dest: Path, name: str) -> None:
    """Generic person + an overlaid knife above the head + a name label (non-graphic)."""
    person_src = IMAGES_DIR / "person.jpg"
    base = (
        Image.open(person_src).convert("RGB").resize((512, 512))
        if person_src.exists()
        else Image.new("RGB", (512, 512), (110, 110, 120))
    )

    knife_src = IMAGES_DIR / "knife.jpg"
    if knife_src.exists():
        knife = Image.open(knife_src).convert("RGB").rotate(90, expand=True)
        knife = knife.resize((220, 150))
        base.paste(knife, (int((512 - 220) / 2), 6))

    d = ImageDraw.Draw(base)
    # name banner along the bottom
    d.rectangle([0, 452, 512, 512], fill=(0, 0, 0))
    _centered(d, 462, name.upper(), font(40), (255, 255, 255), 512)
    base.save(dest)


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    make_kill_note(IMAGES_DIR / "threat_kill_note.png", "Jay Jajoo")
    print("  wrote threat_kill_note.png (name + KILL text)")
    make_person_knife(IMAGES_DIR / "person_knife_named.png", "Marcus Webb")
    print("  wrote person_knife_named.png (person + knife + name)")


if __name__ == "__main__":
    main()
