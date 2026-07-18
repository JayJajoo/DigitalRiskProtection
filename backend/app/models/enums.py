"""Shared enumerations for the DRP domain models."""

from __future__ import annotations

from enum import Enum


class CustomerType(str, Enum):
    person = "person"
    company = "company"


class AssetType(str, Enum):
    email = "email"
    phone = "phone"
    address = "address"
    domain = "domain"
    website = "website"
    social_handle = "social_handle"
    brand = "brand"
    executive = "executive"
    app = "app"
    credit_card = "credit_card"      # synthetic/test values only
    bank_account = "bank_account"    # synthetic/test values only
    other = "other"


class ConcernType(str, Enum):
    physical_attack = "physical_attack"
    online_threat = "online_threat"
    impersonation = "impersonation"
    data_leak = "data_leak"
    financial_fraud = "financial_fraud"
    scam = "scam"
    phishing = "phishing"
    doxxing = "doxxing"
    mention = "mention"


class ContentType(str, Enum):
    text = "text"
    image = "image"
    text_image = "text+image"


class ContentOrigin(str, Enum):
    real = "real"
    synthetic = "synthetic"


class Sentiment(str, Enum):
    negative = "negative"
    neutral = "neutral"
    positive = "positive"


class Severity(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class MatchSource(str, Enum):
    vector = "vector"
    exact = "exact"
    fuzzy = "fuzzy"
