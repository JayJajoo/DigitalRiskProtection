"""Populate data/images/ for the corpus image items.

For each category we try, in order:
  1. Openverse (openverse.org) — CC0 / public-domain image search API (no key, mature filtered out).
  2. Lorem Picsum — a realistic open photo (for generic scenes only).
  3. A locally-generated Pillow placeholder (always works offline).

This fetches OBJECT images for the flagged categories (a knife, cash) so the vision-enrichment
step has real content to detect — it does NOT fetch graphic/violent/illegal material.

Run:  python data/seed/download_images.py
Output: data/images/*.jpg|png   (gitignored)
"""

from __future__ import annotations

import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

DATA_DIR = Path(__file__).resolve().parent.parent  # backend/data
IMAGES_DIR = DATA_DIR / "images"
UA = {"User-Agent": "drp-seed/0.1 (defensive-security demo)"}

# filename -> (openverse query, picsum seed or None, placeholder label, placeholder colour)
# Object shots exercise specific detections; the "complex scene" set gives realistic,
# multi-person / multi-object real-life images (picsum fallback guarantees a real photo).
TARGETS = {
    # focused object / subject shots
    "person.jpg": ("person portrait face", "drp-person", "PERSON", (90, 90, 110)),
    "building.jpg": ("office building exterior", "drp-building", "BUILDING", (80, 95, 110)),
    "knife.jpg": ("kitchen knife", None, "KNIFE (placeholder)", (60, 63, 70)),
    "cash.jpg": ("stack of cash banknotes", None, "CASH (placeholder)", (34, 92, 54)),
    # complex real-life scenes
    "street_scene.jpg": ("busy city street people traffic", "drp-street", "STREET", (70, 74, 82)),
    "nature.jpg": ("nature landscape mountains forest river", "drp-nature", "NATURE", (46, 82, 60)),
    "crowd.jpg": ("crowd of people outdoor event concert", "drp-crowd", "CROWD", (78, 70, 86)),
    "protest.jpg": ("protest demonstration march street signs", "drp-protest", "PROTEST", (86, 66, 60)),
    "gathering.jpg": ("friends gathering outdoors park picnic", "drp-gathering", "GATHERING", (72, 82, 70)),
}
# Always local (don't fetch a real face for the owner's avatar).
SELF_AVATAR = ("self_avatar.png", "JJ", (37, 99, 235))


def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def is_valid_image(data: bytes) -> bool:
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:  # noqa: BLE001
        return False


def openverse_urls(query: str) -> list[str]:
    # Open licences only (public domain + CC attribution variants); mature results excluded.
    q = urllib.parse.urlencode(
        {"q": query, "license": "cc0,pdm,by,by-sa", "page_size": 5, "mature": "false"}
    )
    url = f"https://api.openverse.org/v1/images/?{q}"
    try:
        payload = json.loads(http_get(url).decode("utf-8"))
        return [r["url"] for r in payload.get("results", []) if r.get("url")]
    except Exception as exc:  # noqa: BLE001
        print(f"    openverse lookup failed ({exc})")
        return []


def try_download(url: str, dest: Path) -> bool:
    try:
        data = http_get(url)
    except Exception as exc:  # noqa: BLE001
        print(f"    download failed ({exc})")
        return False
    if not is_valid_image(data):
        print("    skipped (not a valid image)")
        return False
    dest.write_bytes(data)
    return True


def make_placeholder(dest: Path, text: str, bg: tuple[int, int, int]) -> None:
    img = Image.new("RGB", (512, 512), bg)
    draw = ImageDraw.Draw(img)
    tb = draw.textbbox((0, 0), text)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    draw.text(((512 - tw) / 2, (512 - th) / 2), text, fill=(255, 255, 255))
    if dest.suffix.lower() in (".jpg", ".jpeg"):
        img.save(dest, "JPEG")
    else:
        img.save(dest)


def fetch_category(name: str, query: str, picsum_seed: str | None,
                   label: str, colour: tuple[int, int, int]) -> None:
    dest = IMAGES_DIR / name
    print(f"  {name}: openverse '{query}'")
    for url in openverse_urls(query):
        if try_download(url, dest):
            print(f"    -> openverse ok")
            return
    if picsum_seed:
        if try_download(f"https://picsum.photos/seed/{picsum_seed}/512/512", dest):
            print(f"    -> picsum fallback")
            return
    make_placeholder(dest, label, colour)
    print(f"    -> placeholder")


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for name, (query, seed, label, colour) in TARGETS.items():
        fetch_category(name, query, seed, label, colour)

    av_name, av_label, av_colour = SELF_AVATAR
    make_placeholder(IMAGES_DIR / av_name, av_label, av_colour)
    print(f"  {av_name}: placeholder (owner avatar)")

    print(f"Images ready in {IMAGES_DIR}")


if __name__ == "__main__":
    main()
