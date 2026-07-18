"""Generate a rich, context-heavy description for an entity from its fields + fabricated
'dummy' business/personal details (HQ, revenue, headcount, fame, reach).

Deterministic per entity (seeded by name) so it's stable across runs. Used both to enrich the
seed profiles and to describe newly-created customers, and fed into the asset embeddings.
"""

from __future__ import annotations

import hashlib
import random

CITIES = [
    "Austin, Texas, USA", "London, UK", "Berlin, Germany", "Singapore",
    "Toronto, Canada", "San Francisco, USA", "Bengaluru, India", "Sydney, Australia",
    "Amsterdam, Netherlands", "Dubai, UAE", "Dublin, Ireland", "Tokyo, Japan",
    "São Paulo, Brazil", "Stockholm, Sweden", "Cape Town, South Africa", "Manchester, UK",
]

COMPANY_FAME = {
    "bank": "its app-only current accounts and instant transfers",
    "fintech": "its app-only current accounts and instant transfers",
    "pay": "its one-tap checkout and peer-to-peer payments",
    "crypto": "its low-fee token trading and staking products",
    "insurance": "its usage-based policies and fast claims processing",
    "airline": "its ultra-low-cost fares and dense regional network",
    "travel": "its last-minute deals and loyalty program",
    "logistics": "its same-day delivery network",
    "gaming": "its hit multiplayer titles and live-service updates",
    "media": "its original streaming series",
    "streaming": "its original streaming series and live sports",
    "energy": "its clean-energy plans and smart-home integrations",
    "health": "its telehealth platform and at-home diagnostics",
    "food": "its rapid grocery and meal delivery",
    "cloud": "its developer tooling and managed hosting",
    "saas": "its workflow-automation suite",
    "retail": "its curated online marketplace",
    "ecommerce": "its curated online marketplace and fast shipping",
    "robotics": "its warehouse-automation robots and industrial arms",
    "automotive": "its electric drivetrains and connected-car software",
    "telecom": "its nationwide fiber and 5G network",
    "real estate": "its digital home-buying platform",
    "edtech": "its online certification courses",
    "security": "its threat-detection platform",
    "pharmacy": "its mail-order prescriptions and same-day pickup",
}

PERSON_FAME = [
    "a chart-topping run and sold-out tours",
    "a record-breaking season and a youth sports charity",
    "a viral travel-and-lifestyle following",
    "award-winning investigative reporting",
    "a blockbuster franchise role",
    "a wildly popular live-streaming channel",
    "a best-selling debut album",
    "a landmark championship win and endorsement deals",
]

SPOUSES = [
    ("Dara Lindqvist", "a billionaire tech investor"),
    ("Ravi Anand", "an award-winning film producer"),
    ("Camille Dubois", "a celebrated fashion designer"),
    ("Mateo Alvarez", "a Grammy-winning music producer"),
    ("Hannah Cole", "a bestselling novelist"),
    ("Yuki Tanaka", "a Formula 1 team principal"),
    ("Sofia Marchetti", "a real-estate magnate"),
    ("Idris Bello", "a star NBA point guard"),
]

CARS = [
    "a Porsche 911 and a Range Rover", "two Teslas and a vintage Mercedes",
    "a Bentley Continental GT", "a Ferrari Roma and a Rivian R1S",
    "a matte-black Mercedes G-Wagon", "a Lamborghini Urus",
    "an Aston Martin DB11", "a classic Jaguar E-Type and a Cadillac Escalade",
]

NET_WORTH = ["$4M", "$18M", "$45M", "$120M", "$310M", "$1.2B"]

BACKERS = [
    "backed by top-tier venture investors", "listed on the NASDAQ",
    "privately held by its founders", "part of a larger holding group",
    "recently valued at over $1B in its latest round",
]


def _rng(seed_text: str) -> random.Random:
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest(), 16)
    return random.Random(h)


def rich_description(e: dict) -> str:
    name = e.get("name", "")
    typ = e.get("type", "company")
    industry = (e.get("industry") or "").strip()
    assets = e.get("assets", [])
    rng = _rng(f"{name}|{industry}")

    concerns: list[str] = []
    atypes: list[str] = []
    domain = brand = executive = handle = None
    for a in assets:
        t = a.get("type", "")
        pretty = t.replace("_", " ")
        if pretty not in atypes:
            atypes.append(pretty)
        for c in a.get("concerns", []):
            ct = (c.get("type") or "").replace("_", " ")
            if ct and ct not in concerns:
                concerns.append(ct)
        v = a.get("value", "")
        if t in ("domain", "website") and not domain:
            domain = v
        elif t == "brand" and not brand:
            brand = v
        elif t == "executive" and not executive:
            executive = v
        elif t == "social_handle" and not handle:
            handle = v

    city = rng.choice(CITIES)
    founded = rng.randint(2005, 2021)

    if typ == "company":
        employees = rng.choice([80, 140, 320, 600, 1200, 2400, 5200, 9800])
        size = (
            "an early-stage startup" if employees < 200
            else "a fast-growing scale-up" if employees < 1000
            else "a mid-size firm" if employees < 5000
            else "a large enterprise"
        )
        rev_val = rng.choice([12, 34, 68, 130, 290, 540, 890, 1600])
        revenue = f"${rev_val}M" if rev_val < 1000 else f"${rev_val / 1000:.1f}B"
        customers = rng.choice([0.4, 1.2, 3.5, 6.2, 12, 28])
        backer = rng.choice(BACKERS)
        key = next((k for k in COMPANY_FAME if k in industry.lower()), None)
        fame = COMPANY_FAME.get(key, "its flagship platform and rapid growth")
        lead = (
            f"{name} is {size}" + (f" in {industry.lower()}" if industry else "")
            + f", founded in {founded} and headquartered in {city}. "
            f"It employs roughly {employees:,} people, reports about {revenue} in annual revenue, "
            f"and is {backer}. It is best known for {fame}, serving an estimated {customers} million customers."
        )
        who = []
        if domain:
            who.append(f"online at {domain}")
        if brand:
            who.append(f"under the brand {brand}")
        if handle:
            who.append(f"on social as {handle}")
        if executive:
            who.append(f"led by CEO {executive}")
        who_str = (" It operates " + ", ".join(who) + ".") if who else ""
    else:
        followers = rng.choice([0.3, 0.9, 2.1, 4.3, 8.7, 15])
        role = industry.lower() if industry else "public figure"
        fame = rng.choice(PERSON_FAME)
        spouse = rng.choice(SPOUSES)
        cars = rng.choice(CARS)
        networth = rng.choice(NET_WORTH)
        first = name.split()[0] if name.split() else name
        lead = (
            f"{name} is a {role} based in {city}, best known for {fame}. "
            f"They have an estimated {followers} million followers across platforms and have been "
            f"active publicly since {founded}. {first} is married to {spouse[0]}, {spouse[1]}, has an "
            f"estimated net worth of {networth}, and is often seen driving {cars}."
        )
        who = []
        if handle:
            who.append(f"active on social as {handle}")
        if domain:
            who.append(f"with an official site at {domain}")
        if brand:
            who.append(f"associated with the brand {brand}")
        who_str = (" They are " + ", ".join(who) + ".") if who else ""

    footprint = ", ".join(atypes) if atypes else "several digital assets"
    risks = ", ".join(concerns) if concerns else "various online threats"
    tail = (
        f" Monitored assets include {footprint}; tracked digital-risk threats include {risks}."
    )
    return lead + who_str + tail
