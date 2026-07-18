"""Give every entity a richer `description` (context), generated from its own fields.

The description is used (alongside the asset's unique info) to build each asset's embedding, so
semantic / descriptive threats match far better. Idempotent: regenerates from structured fields.

Run:  python data/seed/enrich_descriptions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]  # backend/
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.entity_profile import rich_description  # noqa: E402

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def _process(path: Path, is_array: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    entities = data if is_array else [data]
    for e in entities:
        e["description"] = rich_description(e)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return len(entities)


def main() -> None:
    total = 0
    self_path = PROFILES_DIR / "self.private.json"
    if self_path.exists():
        total += _process(self_path, is_array=False)
        print("  enriched self.private.json")
    for p in sorted(PROFILES_DIR.glob("entities*.json")):
        n = _process(p, is_array=True)
        total += n
        print(f"  enriched {p.name} ({n})")
    print(f"Rewrote descriptions for {total} entities.")


if __name__ == "__main__":
    main()
