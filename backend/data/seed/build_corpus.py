"""Generate the synthetic Part-2 content corpus.

Reads the entity profiles (self.private.json if present + entities.fake.json) and emits
labelled content items that reference each asset's value, so both the vector and
exact/fuzzy string-match paths have something to hit.

Safety: this generates scam/phishing/impersonation/doxxing *samples* for a defensive
detection demo. It does NOT fabricate graphic or violent threats; "physical safety"
concerns are represented clinically (e.g. address exposure = doxxing).

Run:  python data/seed/build_corpus.py
Output: data/corpus/corpus.json   (gitignored)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent  # backend/data
PROFILES_DIR = DATA_DIR / "profiles"
CORPUS_DIR = DATA_DIR / "corpus"


def load_entities() -> list[dict]:
    entities: list[dict] = []
    self_path = PROFILES_DIR / "self.private.json"
    if self_path.exists():
        entities.append(json.loads(self_path.read_text(encoding="utf-8")))
    for path in sorted(PROFILES_DIR.glob("entities*.json")):
        entities.extend(json.loads(path.read_text(encoding="utf-8")))
    return entities


def load_hard_items() -> list[dict]:
    """Hand-authored adversarial items dropped in as corpus/hard_*.json."""
    items: list[dict] = []
    for path in sorted(CORPUS_DIR.glob("hard_*.json")):
        items.extend(json.loads(path.read_text(encoding="utf-8")))
    return items


def first_asset(entity: dict, atype: str) -> Optional[dict]:
    for a in entity.get("assets", []):
        if a["type"] == atype:
            return a
    return None


def threat_item_for_asset(entity: dict, asset: dict) -> Optional[tuple[str, str]]:
    """Return (label, text) for a synthetic risk item referencing this asset's value."""
    name = entity["name"]
    value = asset["value"]
    atype = asset["type"]

    if atype == "email":
        user = value.split("@")[0]
        return (
            "phishing",
            f"Dear {user}, we detected an unusual sign-in to your account ({value}) from a new device. "
            f"For your protection, verify your identity within 24 hours or access will be suspended: "
            f"http://account-verify-secure.example/login",
        )
    if atype == "domain":
        spoof = value.replace(".example", "-secure.example")
        return (
            "phishing",
            f"⚠️ Your {value} account has been temporarily limited following a routine security "
            f"review. Confirm your login details to restore full access: https://{spoof}/verify",
        )
    if atype == "website":
        return (
            "impersonation",
            f"\U0001f381 HUGE fan giveaway on {value} today only! Sign in with your email and password to "
            f"claim your prize before midnight \U0001f449 {value.split('/')[0]}.claim-now.example",
        )
    if atype == "social_handle":
        return (
            "scam",
            f"hey it's the REAL {value} \U0001f495 my old account got locked so this is my backup. giving back "
            f"to my day-ones — send $20 and i'll send $200 right back, first 50 only!! dm me \U0001f64f",
        )
    if atype == "brand":
        return (
            "money_flipping",
            f"\U0001f6a8 {value} OFFICIAL GIVEAWAY \U0001f6a8 send $50 to the wallet below and get $500 back "
            f"within 10 minutes. only the first 100 people, don't sleep on this \U0001f4b0",
        )
    if atype == "executive":
        return (
            "impersonation",
            f"Hi, it's {value}. I'm stuck in a meeting and can't call. I need you to grab 5 x $100 gift cards "
            f"for a client right now and text me the codes — keep this confidential, I'll reimburse you today.",
        )
    if atype == "phone":
        return (
            "doxxing",
            f"this guy's been scamming people all week. if you wanna let him know how you feel, here's his "
            f"cell: {value} \U0001f4f1",
        )
    if atype == "address":
        return (
            "doxxing",
            f"found out where this clown actually lives \U0001f440 {value}. somebody should go pay him a visit.",
        )
    if atype == "credit_card":
        return (
            "data_leak",
            f"FRESH FULLZ \U0001f4b3 Visa {value} — exp + cvv + billing included, cardholder {name}. "
            f"$15 each, bulk discounts, escrow ok. dm to buy.",
        )
    if atype == "bank_account":
        return (
            "data_leak",
            f"selling verified bank logs — acct {value} ({name}), balance confirmed. full details in the "
            f"dump, priced per entry. dm for the list.",
        )
    return None


def build() -> list[dict]:
    entities = load_entities()
    items: list[dict] = []
    n = 0

    def add(text: Optional[str], label: str, hint: str, ctype: str = "text",
            image_path: Optional[str] = None) -> None:
        nonlocal n
        n += 1
        items.append({
            "id": f"content-{n:03d}",
            "source": "synthetic-corpus",
            "origin": "synthetic",
            "type": ctype,
            "text": text,
            "image_path": image_path,
            "label": label,
            "targets_hint": hint,
        })

    for e in entities:
        name = e["name"]
        # One risk item per asset (guarantees every asset value appears in the corpus).
        for asset in e.get("assets", []):
            res = threat_item_for_asset(e, asset)
            if res:
                label, text = res
                add(text, label, name)
        # A benign mention (control).
        add(f"honestly {name} came through for me today — super smooth, no issues at all. "
            f"10/10 would recommend \U0001f64c", "benign", name)

    # A couple of vague / ambiguous controls tied to real entity names.
    add("idk man, something about Novabank's emails lately feels off \U0001f440 anyone else "
        "getting weird ones?", "vague", "Novabank")
    add("lowkey don't trust whatever's going on with CryptoNest rn... something's not adding up.",
        "vague", "CryptoNest")

    # ── Image items (reference image files created by download_images.py) ──
    add("is this actually @marcuswebb?? this account keeps DMing me asking to 'invest' with him "
        "\U0001f928", "impersonation", "Marcus Webb",
        ctype="text+image", image_path="images/person.jpg")
    add("turned $200 into $1,400 this weekend with @cryptonest \U0001f911 send yours to the wallet "
        "in my bio and watch it double — don't miss out!!", "money_flipping", "CryptoNest",
        ctype="text+image", image_path="images/cash.jpg")
    add("people like elena ruiz should really be more careful about who they upset. just leaving "
        "this here \U0001f642", "online_threat", "Novabank",
        ctype="text+image", image_path="images/knife.jpg")
    add(None, "benign", "(none)", ctype="image", image_path="images/building.jpg")

    # ── Complex real-life scene images (multi-person / cluttered context) ──
    add("@novabank_support your downtown branch had a line out the door AGAIN today \U0001f624 "
        "do better", "vague", "Novabank", ctype="text+image", image_path="images/street_scene.jpg")
    add("weekend hike, exactly what i needed \U0001f332", "benign", "(none)",
        ctype="text+image", image_path="images/nature.jpg")
    add("heard people are planning to show up at Vertex Robotics HQ this week to 'have a word' "
        "with management \U0001f440", "vague", "Vertex Robotics", ctype="text+image",
        image_path="images/crowd.jpg")
    add("@helios_air cancelled our flight AND lost the bags. half the plane is outside terminal 3 "
        "now. fix this.", "vague", "Helios Airlines", ctype="text+image",
        image_path="images/protest.jpg")
    add("what a night \U0001f3b6 even ran into Priya Sharma at the afterparty!", "benign",
        "Priya Sharma", ctype="text+image", image_path="images/gathering.jpg")

    # ── Image-ONLY threat items: the message lives INSIDE the image. Sonnet vision must OCR
    #    the name + read the scene to detect and attribute the threat (no caption text). ──
    add(None, "physical_threat", "Jay Jajoo", ctype="image",
        image_path="images/threat_kill_note.png")
    add(None, "physical_threat", "Marcus Webb", ctype="image",
        image_path="images/person_knife_named.png")

    # Self-specific image item (only if the self profile is present).
    if any(e["id"] == "cust-self" for e in entities):
        add("hey it's Jay Jajoo — lost access to my old email so reach me at "
            "jayjajoo02.secure@gmail.com now. quick favor, can you resend that invoice payment? "
            "need it done in the next hour \U0001f64f", "impersonation", "Jay Jajoo",
            ctype="text+image", image_path="images/self_avatar.png")

    return items


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    generated = build()
    hard = load_hard_items()
    items = generated + hard
    out = CORPUS_DIR / "corpus.json"
    out.write_text(json.dumps(items, indent=2), encoding="utf-8")
    labels: dict[str, int] = {}
    for it in items:
        labels[it.get("label") or "unlabelled"] = labels.get(it.get("label") or "unlabelled", 0) + 1
    print(f"Wrote {len(items)} content items -> {out} "
          f"({len(generated)} generated + {len(hard)} hard/adversarial)")
    print("By label:", dict(sorted(labels.items())))


if __name__ == "__main__":
    main()
