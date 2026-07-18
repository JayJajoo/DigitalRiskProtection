"""Generate a random synthetic company profile to pre-fill the 'new customer' form."""

from __future__ import annotations

import random
import uuid

from ..models import Asset, Concern, Customer
from .entity_profile import rich_description

COMPANIES = [
    ("Aurora Logistics", "Logistics & shipping"),
    ("Nimbus Cloud", "Cloud / SaaS"),
    ("Ironclad Insurance", "Insurance"),
    ("Verdant Foods", "Food delivery"),
    ("Pulse Fitness", "Fitness & wellness"),
    ("Solstice Energy", "Energy / utilities"),
    ("Cobalt Bank", "Banking"),
    ("Meridian Travel", "Travel & hospitality"),
    ("Quartz Interactive", "Gaming studio"),
    ("Fable Media", "Streaming media"),
]

EXECS = [
    "Dana Whitfield", "Omar Haddad", "Lena Fischer", "Raj Malhotra", "Nora Bennett",
    "Theo Vasquez", "Ingrid Sato", "Marcus Boone", "Priyanka Rao", "Elliot Frost",
]


def _slug(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum()) or "entity"


def random_customer() -> Customer:
    name, industry = random.choice(COMPANIES)
    slug = _slug(name)
    cid = f"cust-new-{slug}-{uuid.uuid4().hex[:6]}"
    domain = f"{slug}.example"

    pool = [
        Asset(id=f"{cid}-domain", type="domain", value=domain,
              concerns=[Concern(type="phishing"), Concern(type="data_leak")]),
        Asset(id=f"{cid}-brand", type="brand", value=name,
              concerns=[Concern(type="impersonation")]),
        Asset(id=f"{cid}-handle", type="social_handle", value=f"@{slug}",
              concerns=[Concern(type="scam")]),
        Asset(id=f"{cid}-email", type="email", value=f"support@{domain}",
              concerns=[Concern(type="phishing")]),
        Asset(id=f"{cid}-exec", type="executive", value=random.choice(EXECS),
              concerns=[Concern(type="impersonation"), Concern(type="online_threat")]),
        Asset(id=f"{cid}-acct", type="bank_account", value=f"ACCT {random.randint(100000000000, 999999999999)}",
              concerns=[Concern(type="data_leak"), Concern(type="financial_fraud")]),
    ]
    # domain + brand always; a random 2-4 of the rest
    assets = pool[:2] + random.sample(pool[2:], k=random.randint(2, 4))

    # Rich description (context) via the shared generator — so new customers embed just as well.
    description = rich_description(
        {
            "name": name,
            "type": "company",
            "industry": industry,
            "assets": [a.model_dump() for a in assets],
        }
    )

    return Customer(
        id=cid,
        name=name,
        type="company",
        industry=industry,
        description=description,
        protect_summary=(
            f"Protect the {name} domain, brand, executives, and accounts from phishing, "
            "impersonation, and data leaks."
        ),
        assets=assets,
    )
