import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app import boundaries
from app.config import get_settings
from app.services.phone_extractor import extract_phone

settings = get_settings()
_PHONEISH_RE = re.compile(r"(?:\+33|0033|0)[\s.()-]*(?:\d[\s.()-]*){3,}")


class NormalizedApifyLead(BaseModel):
    source_platform: str = "other"
    source_item_id: str | None = None
    url: str | None = None
    title: str | None = None
    description: str | None = None
    phone_e164: str | None = None
    price: int | None = None
    mileage: int | None = None
    location: str | None = None
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    seller_type: str | None = None
    confidence: float = 0.0
    status: Literal["actionable", "non_actionable", "rejected", "exception"]
    error_code: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class FieldCandidate:
    path: str
    value: Any
    score: int


def flatten_payload(payload: Any) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    stack: list[tuple[str, Any, int]] = [("", payload, 0)]
    seen: set[int] = set()
    while stack:
        path, value, depth = stack.pop()
        if depth > 100:
            if path:
                flattened[path] = value
            continue
        if isinstance(value, dict):
            identity = id(value)
            if identity in seen:
                continue
            seen.add(identity)
            for key, child in reversed(list(value.items())):
                child_path = f"{path}.{key}" if path else str(key)
                stack.append((child_path, child, depth + 1))
        elif isinstance(value, (list, tuple)):
            identity = id(value)
            if identity in seen:
                continue
            seen.add(identity)
            for index in range(len(value) - 1, -1, -1):
                child_path = f"{path}[{index}]" if path else f"[{index}]"
                stack.append((child_path, value[index], depth + 1))
        elif path:
            flattened[path] = value
    return flattened


def schema_fingerprint(schema: dict | None) -> str | None:
    if schema is None:
        return None
    encoded = json.dumps(
        schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _schema_contact_paths(schema: dict | None) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    paths: set[str] = set()
    stack: list[tuple[str, dict]] = [("", schema)]
    while stack:
        path, node = stack.pop()
        properties = node.get("properties")
        if not isinstance(properties, dict):
            continue
        for name, child in properties.items():
            if not isinstance(child, dict):
                continue
            child_path = f"{path}.{name}" if path else str(name)
            description = str(child.get("description") or "").lower()
            marker = f"{name} {description} {child.get('format', '')}".lower()
            if any(word in marker for word in ("phone", "telephone", "mobile", "contact")):
                paths.add(child_path)
            stack.append((child_path, child))
    return paths


def _profile_mappings(profile: Any) -> dict[str, str]:
    if profile is None:
        return {}
    mappings = profile.get("mappings", {}) if isinstance(profile, dict) else getattr(
        profile, "mappings", {}
    )
    if not isinstance(mappings, dict):
        return {}
    return {
        str(field): str(path)
        for field, path in mappings.items()
        if isinstance(path, str)
    }


def _key(path: str) -> str:
    return re.sub(r"[^a-z0-9]", "", path.rsplit(".", 1)[-1].lower())


def score_phone_candidate(
    path: str,
    *,
    schema_paths: set[str],
    preferred_path: str | None,
) -> int:
    if preferred_path == path:
        return 110
    if path in schema_paths:
        return 100
    key = _key(path)
    if key.startswith("phone") or key in {
        "tel",
        "telephone",
        "mobile",
        "contactnumber",
        "phonenumber",
    }:
        return 80
    return 40


def _add(
    candidates: dict[str, list[FieldCandidate]],
    field: str,
    path: str,
    value: Any,
    score: int,
) -> None:
    candidates.setdefault(field, []).append(FieldCandidate(path, value, score))


def collect_candidates(
    payload: dict,
    schema: dict | None,
    profile: Any,
) -> dict[str, list[FieldCandidate]]:
    flattened = flatten_payload(payload)
    candidates: dict[str, list[FieldCandidate]] = {}
    mappings = _profile_mappings(profile)
    schema_phone_paths = _schema_contact_paths(schema)
    for path, value in flattened.items():
        text = value if isinstance(value, str) else str(value) if value is not None else ""
        phone = extract_phone(text)
        if phone:
            _add(
                candidates,
                "phone",
                path,
                phone,
                score_phone_candidate(
                    path,
                    schema_paths=schema_phone_paths,
                    preferred_path=mappings.get("phone"),
                ),
            )

        key = _key(path)
        parent = path.rsplit(".", 1)[0].lower() if "." in path else ""
        if isinstance(value, str) and value.strip():
            if key in {"title", "adtitle", "listingtitle"}:
                _add(candidates, "title", path, value.strip(), 80)
            elif key == "name" and any(
                marker in parent for marker in ("vehicle", "listing", "car", "ad")
            ):
                _add(candidates, "title", path, value.strip(), 75)
            if key in {"url", "link", "listingurl", "adurl"}:
                _add(candidates, "url", path, value.strip(), 80)
            if key in {"description", "body", "text", "details"}:
                _add(candidates, "description", path, value.strip(), 80)
            if key in {"location", "city", "address", "region"}:
                _add(candidates, "location", path, value.strip(), 70)
            if key in {"brand", "make", "marque"}:
                _add(candidates, "brand", path, value.strip(), 80)
            if key in {"model", "modele"}:
                _add(candidates, "model", path, value.strip(), 80)
            if key in {"sellertype", "ownertype", "accounttype"}:
                _add(candidates, "seller_type", path, value.strip(), 75)
            if key in {"id", "itemid", "listingid", "adid"}:
                _add(candidates, "source_item_id", path, value.strip(), 60)
        if key in {"price", "prix"}:
            _add(candidates, "price", path, value, 80)
        if key in {"mileage", "kilometers", "kilometres", "km"}:
            _add(candidates, "mileage", path, value, 80)
        if key in {"year", "annee"}:
            _add(candidates, "year", path, value, 80)

    for field, path in mappings.items():
        if field == "phone" or path not in flattened:
            continue
        _add(candidates, field, path, flattened[path], 110)
    return candidates


def _best(candidates: dict[str, list[FieldCandidate]], field: str) -> FieldCandidate | None:
    values = candidates.get(field, [])
    return max(values, key=lambda item: item.score, default=None)


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"-?\d[\d\s.,]*", str(value))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group())
    return int(digits) if digits else None


def infer_source_platform(payload: dict) -> str:
    flattened = flatten_payload(payload)
    for path, value in flattened.items():
        text = str(value).lower()
        if "leboncoin.fr" in text or (_key(path) in {"source", "platform"} and text == "leboncoin"):
            return "leboncoin"
        if "lacentrale.fr" in text or "la_centrale" in text:
            return "la_centrale"
    return "other"


def normalize_apify_item(
    payload: dict,
    *,
    schema: dict | None,
    profile: Any,
) -> NormalizedApifyLead:
    candidates = collect_candidates(payload, schema, profile)
    evidence: dict[str, str] = {}
    phone_candidates = sorted(
        candidates.get("phone", []), key=lambda item: item.score, reverse=True
    )
    unique_phones: list[FieldCandidate] = []
    seen_phones: set[str] = set()
    for candidate in phone_candidates:
        if candidate.value not in seen_phones:
            seen_phones.add(candidate.value)
            unique_phones.append(candidate)
    if len(unique_phones) > 1 and unique_phones[0].score - unique_phones[1].score < 10:
        return NormalizedApifyLead(
            source_platform=infer_source_platform(payload),
            confidence=unique_phones[0].score / 110,
            status="exception",
            error_code="ambiguous_phone",
            evidence={"phone": unique_phones[0].path},
        )

    selected: dict[str, FieldCandidate] = {}
    for field in (
        "title",
        "url",
        "description",
        "price",
        "mileage",
        "location",
        "brand",
        "model",
        "year",
        "seller_type",
        "source_item_id",
    ):
        candidate = _best(candidates, field)
        if candidate is not None:
            selected[field] = candidate
            evidence[field] = candidate.path

    phone = unique_phones[0] if unique_phones else None
    if phone is not None:
        evidence["phone"] = phone.path
    flattened = flatten_payload(payload)
    has_phone_shape = any(
        isinstance(value, str) and _PHONEISH_RE.search(value)
        for value in flattened.values()
    )
    return NormalizedApifyLead(
        source_platform=infer_source_platform(payload),
        source_item_id=str(selected["source_item_id"].value)
        if "source_item_id" in selected
        else None,
        url=str(selected["url"].value) if "url" in selected else None,
        title=str(selected["title"].value) if "title" in selected else None,
        description=str(selected["description"].value)
        if "description" in selected
        else None,
        phone_e164=str(phone.value) if phone is not None else None,
        price=_integer(selected["price"].value) if "price" in selected else None,
        mileage=_integer(selected["mileage"].value)
        if "mileage" in selected
        else None,
        location=str(selected["location"].value) if "location" in selected else None,
        brand=str(selected["brand"].value) if "brand" in selected else None,
        model=str(selected["model"].value) if "model" in selected else None,
        year=_integer(selected["year"].value) if "year" in selected else None,
        seller_type=str(selected["seller_type"].value)
        if "seller_type" in selected
        else None,
        confidence=phone.score / 110 if phone is not None else 0.0,
        status=(
            "actionable"
            if phone is not None
            else "rejected"
            if has_phone_shape
            else "non_actionable"
        ),
        error_code=None if phone is not None else "invalid_phone" if has_phone_shape else None,
        evidence=evidence,
    )


async def normalize_apify_item_with_fallback(
    payload: dict,
    *,
    schema: dict | None,
    profile: Any,
) -> NormalizedApifyLead:
    result = normalize_apify_item(payload, schema=schema, profile=profile)
    if result.status == "actionable" or not settings.apify_ai_fallback_enabled:
        return result
    flattened = flatten_payload(payload)
    if not any(extract_phone(value) for value in flattened.values() if isinstance(value, str)):
        return result
    bounded = {
        path: value
        for path, value in flattened.items()
        if isinstance(value, (str, int, float)) and len(str(value)) <= 2000
    }
    candidate_paths = list(bounded)[:100]
    bounded = {path: bounded[path] for path in candidate_paths}
    inferred = await boundaries.infer_apify_lead_fields(bounded, candidate_paths)
    mappings = _profile_mappings(profile)
    mappings.update(
        {
            field: path
            for field, path in inferred.items()
            if path in flattened
        }
    )
    return normalize_apify_item(
        payload,
        schema=schema,
        profile={"mappings": mappings},
    )
