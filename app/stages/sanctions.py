import re
from typing import Optional
from rapidfuzz import fuzz
from app.schemas import EntityInput, StageResult

# Common corporate suffixes stripped during normalization to prevent false negatives
CORPORATE_SUFFIXES = {
    "llc", "ltd", "limited", "inc", "incorporated", "corp", "corporation",
    "co", "company", "plc", "gmbh", "sa", "ag", "pte", "pvt", "bv", "nv",
}

# Sample watchlist dataset (canonical names, aliases, and secondary attributes)
DEFAULT_WATCHLIST = [
    {
        "watchlist_id": "OFAC-1001",
        "name": "Viktor Petrovich Sokolov",
        "aliases": ["Victor Sokolov", "V. P. Sokolov"],
        "entity_type": "INDIVIDUAL",
        "country": "RU",
        "dob": "1974-08-19",
        "program": "RUSSIA-EO14024",
    },
    {
        "watchlist_id": "OFAC-1002",
        "name": "Al-Noor Trading Group",
        "aliases": ["Al Noor Trading", "Noor Global Trade"],
        "entity_type": "CORPORATE",
        "country": "AE",
        "dob": None,
        "program": "SDGT",
    },
    {
        "watchlist_id": "EU-2045",
        "name": "Caspian Maritime Logistics",
        "aliases": ["Caspian Sea Logistics", "Caspian Freight"],
        "entity_type": "CORPORATE",
        "country": "IR",
        "dob": None,
        "program": "IRAN-TRA",
    },
]


def normalize_entity_name(raw_name: str, entity_type: str = "INDIVIDUAL") -> str:
    """Lowercase, strip punctuation, and remove corporate legal designators."""
    cleaned = re.sub(r"[^\w\s]", " ", raw_name.lower()).strip()
    tokens = [t for t in cleaned.split() if t]
    if entity_type.upper() == "CORPORATE":
        tokens = [t for t in tokens if t not in CORPORATE_SUFFIXES]
    return " ".join(tokens)


def score_against_record(entity: EntityInput, record: dict) -> tuple[float, list[str]]:
    """Compute composite match score (0-100) using fuzzy name + secondary attributes."""
    reasons: list[str] = []
    norm_query = normalize_entity_name(entity.name, entity.entity_type)

    candidates = [record["name"], *record.get("aliases", [])]
    best_name_score = 0.0
    matched_label = record["name"]

    for candidate in candidates:
        norm_cand = normalize_entity_name(candidate, record.get("entity_type", "INDIVIDUAL"))
        # Blend token_sort_ratio (reordered tokens) and WRatio (partial/weighted match)
        ts_score = fuzz.token_sort_ratio(norm_query, norm_cand)
        w_score = fuzz.WRatio(norm_query, norm_cand)
        blended = 0.6 * ts_score + 0.4 * w_score
        if blended > best_name_score:
            best_name_score = blended
            matched_label = candidate

    score = best_name_score
    if best_name_score >= 75.0:
        reasons.append(
            f"Name fuzzy match ({best_name_score:.1f}) against '{matched_label}' [{record['watchlist_id']}]"
        )

    # Secondary attribute adjustments (only apply when both sides have non-null values)
    if entity.country and record.get("country"):
        if entity.country.upper() == record["country"].upper():
            score += 6.0
            reasons.append(f"Country match confirmed ({entity.country.upper()})")
        else:
            score -= 8.0
            reasons.append(
                f"Country mismatch: input={entity.country.upper()} vs watchlist={record['country'].upper()}"
            )

    if entity.dob and record.get("dob"):
        if entity.dob == record["dob"]:
            score += 10.0
            reasons.append(f"Exact DOB match ({entity.dob})")
        else:
            score -= 12.0
            reasons.append(f"DOB conflict: input={entity.dob} vs watchlist={record['dob']}")

    clamped_score = round(max(0.0, min(100.0, score)), 2)
    return clamped_score, reasons


def run_sanctions_stage(
    entity: EntityInput, watchlist: Optional[list[dict]] = None
) -> StageResult:
    """Evaluate an entity against the sanctions watchlist and return structured findings."""
    records = watchlist if watchlist is not None else DEFAULT_WATCHLIST
    best_score = 0.0
    best_reasons: list[str] = []
    best_match: Optional[dict] = None

    for record in records:
        score, reasons = score_against_record(entity, record)
        if score > best_score:
            best_score = score
            best_reasons = reasons
            best_match = record

    if best_score >= 88.0:
        tier = "HIGH_RISK_HIT"
        flagged = True
    elif best_score >= 75.0:
        tier = "MANUAL_REVIEW"
        flagged = True
    else:
        tier = "AUTO_CLEAR"
        flagged = False
        if not best_reasons:
            best_reasons = ["No watchlist candidate exceeded screening threshold (75.0)"]

    return StageResult(
        stage="sanctions_resolution",
        score=best_score,
        flagged=flagged,
        reasons=best_reasons,
        metadata={
            "tier": tier,
            "normalized_query": normalize_entity_name(entity.name, entity.entity_type),
            "matched_watchlist_id": best_match["watchlist_id"] if best_match and flagged else None,
            "program": best_match["program"] if best_match and flagged else None,
        },
    )