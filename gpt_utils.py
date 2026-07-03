import json
import re
import time
from datetime import datetime

import openai
import pandas as pd
import requests
from pgvector.psycopg2 import register_vector

from api.db.connection import connect_db as connect_bootstrap_db
from api.services.app_settings import get_setting_value

MIN_VALID_ITEMS = get_setting_value("labeling.min_valid_items", default=6)
DEFAULT_TOP_POSITIVE_ITEMS = get_setting_value("labeling.default_top_positive_items", default=6)
DEFAULT_TOP_NEGATIVE_ITEMS = get_setting_value("labeling.default_top_negative_items", default=4)
DEFAULT_FETCH_ITEMS = get_setting_value("labeling.default_fetch_items", default=10)
MINIMUM_LABEL_COVERAGE_PERCENT = get_setting_value("labeling.minimum_label_coverage_percent", default=70)
MAXIMUM_LOW_OVERLAP_PERCENT = get_setting_value("labeling.maximum_low_overlap_percent", default=40)
SUMMARY_HINT_CHARS = get_setting_value("labeling.summary_hint_chars", default=220)
MAX_GENRE_TAGS = get_setting_value("labeling.max_genre_tags", default=3)
MAX_CAST_NAMES = get_setting_value("labeling.max_cast_names", default=2)
MAX_DIRECTOR_NAMES = get_setting_value("labeling.max_director_names", default=2)
MAX_ITEMS_PER_USER_IN_PROMPT = get_setting_value("labeling.max_items_per_user_in_prompt", default=2)
EMBEDDING_SIDE_DIMENSIONS = 768
COMBINED_EMBEDDING_DIMENSIONS = EMBEDDING_SIDE_DIMENSIONS * 2
UNCLEAR_LABEL = "UNCLEAR / MIXED SIGNAL"
LABEL_PROVIDER = str(get_setting_value("labeling.provider", default="ollama")).lower()
OPENAI_LABEL_MODEL = get_setting_value("labeling.openai_model", default="gpt-4")
OLLAMA_HOST = str(get_setting_value("ollama.host", default="http://localhost:11434")).rstrip("/")
OLLAMA_LABEL_MODEL = get_setting_value("labeling.ollama_model", default="gemma3")
OLLAMA_TIMEOUT_S = get_setting_value("ollama.timeout_s", default=300)

SYSTEM_PROMPT = """
You label one embedding dimension for film and TV data.

Find the strongest reusable semantic separator between HIGH and LOW examples.
Use all available evidence: titles, genres, media type, plot hints, and cast/director only
when they reveal an obvious cluster.
Genres are often broad and noisy. Plot hints may contain the clearest signal for story/entity
dimensions, so a repeated plot concept can be the primary basis for the label.

For media dimensions, identify a concrete item-side separator and label the title/content trait.
For user dimensions, infer a viewer preference, taste, affinity, or tendency from the representative
watches associated with HIGH versus LOW users. User-dimension labels must be preference-framed;
do not label them as direct title/content traits.

Prefer concrete story/entity separators over broad genre labels.
Bad labels are broad genre summaries, such as "sci-fi action", "speculative themes", or
"complex narratives".
Good media labels are short, concrete, evidence-derived noun phrases.
Good user labels are short, concrete, preference-framed phrases such as "preference for workplace comedy"
or "viewer affinity for relationship-driven stories".
Do not copy example wording from these instructions into the label. The label must come only
from the HIGH/LOW evidence for the current dimension.
If related dimensions share a broad theme, label each dimension by its distinguishing nuance
instead of reusing a generic umbrella label.

Avoid abstract trope language unless it is clearly supported by multiple items.
Do not use labels like redemption, coming of age, relationships, secrets, truth, purpose,
humanity, moral ambiguity, family healing, or similar moral-arc language unless the pattern is
explicitly repeated across several items and clearly separates HIGH from LOW.

Do not return UNCLEAR / MIXED SIGNAL merely because the label is imperfect.
If one or two HIGH examples are outliers but the remaining examples form a clear cluster,
label the dominant cluster and lower confidence.

Use UNCLEAR / MIXED SIGNAL only when no concrete label reaches the coverage threshold or
HIGH and LOW examples are not meaningfully separable:
UNCLEAR / MIXED SIGNAL

Return JSON only.
""".strip()

USER_PROMPT_TEMPLATE = """
Task:
Label embedding dimension {dimension} using HIGH vs LOW contrast.

Dimension type:
{dimension_scope}

Dimension-specific guidance:
{dimension_specific_guidance}

{review_context}
Rules:
- Find the strongest reusable semantic separator between HIGH and LOW examples.
- Use all available evidence: titles, genres, media type, plot hints, and cast/director only when they reveal an obvious cluster.
- Genres are often broad and noisy; do not over-weight genre if plot hints reveal a stronger common concept.
- Prefer concrete story/entity labels over broad genre labels.
- Bad label style: "sci-fi action", "speculative themes", or "complex narratives".
{label_style_guidance}
- Derive the label only from the listed HIGH/LOW items for this dimension.
- Never copy wording from these instructions or reuse a prior label unless the current dimension independently supports the exact words.
- When a dimension resembles a broader theme seen elsewhere, choose the narrower nuance that best separates this HIGH set from this LOW set.
- Label must be 8 words or fewer.
- Explanation must be exactly 1 sentence.
- Provide exactly 3 evidence bullets as short strings.
- Each evidence bullet must cite repeated patterns from the items, not vague themes.
- If LOW items are present, explain what separates HIGH from LOW.
- If fewer than {min_valid_items} valid HIGH items remain, output UNCLEAR / MIXED SIGNAL.
- Before assigning a label, estimate how many HIGH examples support the proposed label and how many LOW examples also match it.
- Use Minimum Label Coverage Percent = {minimum_label_coverage_percent}.
- Use Maximum Low Overlap Percent = {maximum_low_overlap_percent}.
- HIGH examples in this prompt = {high_item_count}; LOW examples in this prompt = {low_item_count}.
- A proposed label is only strong if HIGH coverage is at or above {minimum_label_coverage_percent}% and LOW overlap is at or below {maximum_low_overlap_percent}%.
- If fewer than {minimum_label_coverage_percent}% of HIGH examples clearly support the proposed label, do not assign a confident semantic label.
- If one or two HIGH examples are outliers but the remaining examples form a clear cluster, assign the dominant cluster label and lower confidence.
- When coverage is far below the threshold, return UNCLEAR / MIXED SIGNAL unless there is an obvious narrow cluster label such as "Gossip Girl episode cluster" or "mostly short episodic titles"; narrow cluster labels should be low or medium confidence.
- If LOW overlap is above {maximum_low_overlap_percent}%, the label cannot be high confidence.
- If LOW overlap is 50% or higher, return UNCLEAR / MIXED SIGNAL unless the label is a very narrow mechanical label that is still clearly useful.
- Do not claim broad labels based on only a minority of examples.
- Do not assign broad semantic labels that apply equally well to HIGH and LOW examples.
- Prefer labels that separate HIGH from LOW, not merely labels that describe HIGH.
- Prefer concrete semantic labels over broad genres, mechanical labels, or creative vibe labels.
- Report coverage as counts and percents: coverage_high_count / coverage_high_total and coverage_low_overlap_count / coverage_low_total, such as 7/10 and 2/8.
- Return UNCLEAR / MIXED SIGNAL only if:
  1. no concrete label reaches the coverage threshold after allowing a dominant cluster with one or two outliers,
  2. malformed or truncated titles dominate,
  3. HIGH vs LOW contrast is weak or contradictory.

Return ONLY this JSON shape:
{{
  "label": "short label or UNCLEAR / MIXED SIGNAL",
  "label_confidence": "high, medium, low, or unclear",
  "proposed_label_type": "semantic, cluster, mechanical, or unclear",
  "coverage_high_count": 0,
  "coverage_high_total": 0,
  "coverage_high_percent": 0,
  "coverage_low_overlap_count": 0,
  "coverage_low_total": 0,
  "coverage_low_overlap_percent": 0,
  "explanation": "One sentence explaining the separator.",
  "evidence": [
    "bullet 1",
    "bullet 2",
    "bullet 3"
  ]
}}

HIGH ITEMS:
{top_positive_block}

LOW ITEMS:
{top_negative_block}
""".strip()

USER_PREFERENCE_FRAMING_RE = re.compile(
    r"\b("
    r"preference|preferences|affinity|affinities|taste|tastes|tendency|tendencies|"
    r"interest|interests|interested\s+in|gravitates?\s+toward|gravitates?\s+towards|"
    r"drawn\s+to|leans?\s+toward|leans?\s+towards|viewer\s+affinity|viewer\s+taste|"
    r"viewer\s+preference"
    r")\b",
    flags=re.IGNORECASE,
)
NON_SEMANTIC_LABEL_FRAGMENT_RE = re.compile(
    r"\b("
    r"unclear|mixed signal|non[-\s]+explainable|not explainable|structural|mechanical|"
    r"runtime|release year|released in|metadata|malformed|truncated"
    r")\b",
    flags=re.IGNORECASE,
)
STRUCTURAL_LABEL_RE = re.compile(
    r"(^|[^a-z0-9])("
    r"episode|episodes|season|seasons|tv|television|movie|movies|film|films|"
    r"title|titles|runtime|runtimes"
    r")([^a-z0-9]|$)",
    flags=re.IGNORECASE,
)


def connect_db():
    conn = connect_bootstrap_db()
    register_vector(conn)
    return conn


def resolve_label_backend(provider: str | None = None, model: str | None = None):
    resolved_provider = (provider or LABEL_PROVIDER or "ollama").strip().lower()
    if resolved_provider not in {"openai", "ollama"}:
        raise ValueError(f"Unsupported label provider: {resolved_provider}")

    if resolved_provider == "openai":
        resolved_model = (model or OPENAI_LABEL_MODEL or "gpt-4").strip()
    else:
        resolved_model = (model or OLLAMA_LABEL_MODEL or "gemma3").strip()

    if not resolved_model:
        raise ValueError(f"No model configured for provider: {resolved_provider}")

    return resolved_provider, resolved_model


def _safe_str(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _clean_whitespace(value) -> str:
    return re.sub(r"\s+", " ", _safe_str(value)).strip()


def _normalize_compare_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_whitespace(value).lower()).strip()


def _split_title_parts(value: str) -> list[str]:
    return [part for part in (_clean_whitespace(chunk) for chunk in _safe_str(value).split(":")) if part]


def _collapse_repeated_title_parts(parts: list[str]) -> list[str]:
    if not parts:
        return []

    collapsed = []
    for part in parts:
        if collapsed and _normalize_compare_text(collapsed[-1]) == _normalize_compare_text(part):
            continue
        collapsed.append(part)

    normalized = [_normalize_compare_text(part) for part in collapsed]
    for segment_size in range(1, len(collapsed) // 2 + 1):
        if len(collapsed) != segment_size * 2:
            continue
        if normalized[:segment_size] == normalized[segment_size:]:
            return collapsed[:segment_size]
    return collapsed


def _has_repeated_title_sequence(value: str) -> bool:
    parts = _split_title_parts(value)
    if len(parts) < 2:
        return False
    return _collapse_repeated_title_parts(parts) != parts


def _trim_text(value: str, max_chars: int) -> str:
    cleaned = _clean_whitespace(value).rstrip(".")
    if len(cleaned) <= max_chars:
        return cleaned
    trimmed = cleaned[:max_chars].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed.rstrip(" ,;:.") + "..."


def _split_tags(value: str, limit: int) -> list[str]:
    return [tag for tag in (_clean_whitespace(item) for item in _safe_str(value).split(",")) if tag][:limit]


def _format_year(value) -> str:
    year_text = _clean_whitespace(value)
    if not year_text:
        return "unknown"
    if year_text.endswith(".0"):
        year_text = year_text[:-2]
    return year_text or "unknown"


def _format_runtime(value) -> str:
    raw_value = _clean_whitespace(value)
    if not raw_value:
        return "Unknown"
    try:
        runtime_value = float(raw_value)
    except ValueError:
        return "Unknown"

    if runtime_value <= 0:
        return "Unknown"

    minutes = runtime_value / 60000.0 if runtime_value > 1000 else runtime_value
    rounded_minutes = int(round(minutes))
    if rounded_minutes <= 0:
        return "Unknown"
    return f"{rounded_minutes}m"


def _coerce_label(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(label or "")).strip().strip("\"'")
    cleaned = cleaned.rstrip(".")
    if not cleaned:
        raise ValueError("Label response was empty")
    if len(cleaned) > 120:
        cleaned = cleaned[:120].rstrip()
    return cleaned


def _coerce_explanation(explanation: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(explanation or "")).strip().strip("\"'")
    if not cleaned:
        return ""
    if len(cleaned) > 320:
        cleaned = cleaned[:320].rstrip()
        if " " in cleaned:
            cleaned = cleaned.rsplit(" ", 1)[0]
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _coerce_evidence(evidence) -> list[str]:
    if isinstance(evidence, list):
        cleaned = [re.sub(r"^\-\s*", "", _clean_whitespace(item)) for item in evidence]
    elif isinstance(evidence, str):
        cleaned = [re.sub(r"^\-\s*", "", _clean_whitespace(item)) for item in re.split(r"[\n;]+", evidence)]
    else:
        cleaned = []

    cleaned = [item for item in cleaned if item]
    while len(cleaned) < 3:
        cleaned.append("")
    return cleaned[:3]


def _coerce_optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_label_confidence(value) -> str:
    cleaned = _clean_whitespace(value).lower()
    return cleaned if cleaned in {"high", "medium", "low", "unclear"} else ""


def _coerce_label_type(value) -> str:
    cleaned = _clean_whitespace(value).lower()
    return cleaned if cleaned in {"semantic", "cluster", "mechanical", "unclear"} else ""


def _calculate_percent(count: int | None, total: int | None) -> int | None:
    if count is None or total is None:
        return None
    if total == 0:
        return 0
    return round((count / total) * 100)


def _is_unclear_label(label: str) -> bool:
    return _clean_whitespace(label).lower() == UNCLEAR_LABEL.lower()


def is_user_preference_framed_label(label: str) -> bool:
    return bool(USER_PREFERENCE_FRAMING_RE.search(_clean_whitespace(label)))


def _is_nonsemantic_or_structural_label(label: str, label_type: str | None = None) -> bool:
    cleaned_label = _clean_whitespace(label)
    cleaned_type = _clean_whitespace(label_type).lower()
    if not cleaned_label:
        return True
    if _is_unclear_label(cleaned_label):
        return True
    if cleaned_type in {"unclear", "mechanical"}:
        return True
    if NON_SEMANTIC_LABEL_FRAGMENT_RE.search(cleaned_label):
        return True
    return bool(STRUCTURAL_LABEL_RE.search(cleaned_label))


def _set_validation_status(result: dict, status: str) -> None:
    status_order = {
        "valid": 0,
        "needs_review": 1,
        "downgraded": 2,
        "invalid": 3,
    }
    current = result.get("validation_status", "valid")
    if status_order.get(status, 0) > status_order.get(current, 0):
        result["validation_status"] = status


def _add_validation_note(result: dict, status: str, note: str) -> None:
    _set_validation_status(result, status)
    notes = result.setdefault("validation_notes", [])
    if note and note not in notes:
        notes.append(note)


def validate_label_perspective(result: dict, dimension_mode: str = "media") -> dict:
    validated = dict(result)
    validated["validation_notes"] = list(result.get("validation_notes") or [])

    if dimension_mode != "user":
        return validated

    label = validated.get("label", "")
    label_type = validated.get("label_type") or validated.get("proposed_label_type")
    if _is_nonsemantic_or_structural_label(label, label_type):
        return validated
    if is_user_preference_framed_label(label):
        return validated

    if validated.get("label_confidence") == "high":
        validated["label_confidence"] = "medium"
    _add_validation_note(
        validated,
        "invalid",
        (
            "USER dimension label lacks preference/taste/affinity framing; "
            "plain title-trait labels are not saved for user preference dimensions."
        ),
    )
    return validated


def validate_label_result(
    result: dict,
    minimum_label_coverage_percent: int = MINIMUM_LABEL_COVERAGE_PERCENT,
    maximum_low_overlap_percent: int = MAXIMUM_LOW_OVERLAP_PERCENT,
    dimension_mode: str = "media",
) -> dict:
    validated = dict(result)
    validated["validation_status"] = "valid"
    validated["validation_notes"] = list(result.get("validation_notes") or [])

    high_percent = validated.get("coverage_high_percent")
    low_overlap_percent = validated.get("coverage_low_overlap_percent")

    if high_percent is None:
        _add_validation_note(
            validated,
            "needs_review",
            "HIGH coverage percent was missing or unparsable; review recommended.",
        )
    if low_overlap_percent is None:
        _add_validation_note(
            validated,
            "needs_review",
            "LOW overlap percent was missing or unparsable; review recommended.",
        )

    if low_overlap_percent is not None and low_overlap_percent > maximum_low_overlap_percent:
        if low_overlap_percent >= 50:
            validated["label"] = UNCLEAR_LABEL
            validated["label_confidence"] = "unclear"
            validated["label_type"] = "unclear"
            validated["proposed_label_type"] = "unclear"
            _add_validation_note(
                validated,
                "invalid",
                (
                    f"LOW-side overlap was {low_overlap_percent}%, above the "
                    f"{maximum_low_overlap_percent}% maximum; label does not clearly separate HIGH from LOW."
                ),
            )
        else:
            if validated.get("label_confidence") == "high":
                validated["label_confidence"] = "medium"
            elif not validated.get("label_confidence"):
                validated["label_confidence"] = "low"
            _add_validation_note(
                validated,
                "downgraded",
                (
                    f"LOW-side overlap was {low_overlap_percent}%, above the "
                    f"{maximum_low_overlap_percent}% maximum; confidence was downgraded."
                ),
            )

    if (
        high_percent is not None
        and high_percent < minimum_label_coverage_percent
        and not _is_unclear_label(validated.get("label", ""))
    ):
        near_threshold_floor = max(0, minimum_label_coverage_percent - 10)
        is_near_threshold = high_percent >= near_threshold_floor
        low_overlap_is_limited = (
            low_overlap_percent is None
            or low_overlap_percent <= maximum_low_overlap_percent
        )

        if (
            validated.get("label_type") in {"cluster", "mechanical"}
            or (is_near_threshold and low_overlap_is_limited)
        ):
            validated["label_confidence"] = "low"
            _add_validation_note(
                validated,
                "downgraded",
                (
                    f"HIGH coverage was {high_percent}%, below the "
                    f"{minimum_label_coverage_percent}% preferred minimum; kept only as a low-confidence "
                    f"dominant-cluster label."
                ),
            )
        else:
            validated["label"] = UNCLEAR_LABEL
            validated["label_confidence"] = "unclear"
            validated["label_type"] = "unclear"
            validated["proposed_label_type"] = "unclear"
            _add_validation_note(
                validated,
                "invalid",
                (
                    f"HIGH coverage was {high_percent}%, below the "
                    f"{minimum_label_coverage_percent}% minimum; label was downgraded to UNCLEAR / MIXED SIGNAL."
                ),
            )

    low_overlap_blocks_unclear_review = (
        low_overlap_percent is not None and low_overlap_percent > maximum_low_overlap_percent
    )
    if (
        _is_unclear_label(validated.get("label", ""))
        and high_percent is not None
        and high_percent >= minimum_label_coverage_percent
        and not low_overlap_blocks_unclear_review
    ):
        _add_validation_note(
            validated,
            "needs_review",
            (
                "Label marked unclear despite meeting HIGH coverage threshold; "
                "review recommended."
            ),
        )

    return validate_label_perspective(validated, dimension_mode=dimension_mode)


def _normalize_label_result(
    label: str,
    explanation: str = "",
    evidence=None,
    coverage_high_count=None,
    coverage_high_total=None,
    coverage_high_percent=None,
    coverage_low_overlap_count=None,
    coverage_low_total=None,
    coverage_low_overlap_percent=None,
    label_confidence=None,
    label_type=None,
    minimum_label_coverage_percent: int = MINIMUM_LABEL_COVERAGE_PERCENT,
    maximum_low_overlap_percent: int = MAXIMUM_LOW_OVERLAP_PERCENT,
    dimension_mode: str = "media",
) -> dict:
    normalized_high_count = _coerce_optional_int(coverage_high_count)
    normalized_high_total = _coerce_optional_int(coverage_high_total)
    normalized_high_percent = _coerce_optional_int(coverage_high_percent)
    if normalized_high_percent is None:
        normalized_high_percent = _calculate_percent(normalized_high_count, normalized_high_total)

    normalized_low_count = _coerce_optional_int(coverage_low_overlap_count)
    normalized_low_total = _coerce_optional_int(coverage_low_total)
    normalized_low_percent = _coerce_optional_int(coverage_low_overlap_percent)
    if normalized_low_percent is None:
        normalized_low_percent = _calculate_percent(normalized_low_count, normalized_low_total)

    proposed_label_type = _coerce_label_type(label_type)
    normalized = {
        "label": _coerce_label(label),
        "label_confidence": _coerce_label_confidence(label_confidence),
        "label_type": proposed_label_type,
        "proposed_label_type": proposed_label_type,
        "coverage_high_count": normalized_high_count,
        "coverage_high_total": normalized_high_total,
        "coverage_high_percent": normalized_high_percent,
        "coverage_low_overlap_count": normalized_low_count,
        "coverage_low_total": normalized_low_total,
        "coverage_low_overlap_percent": normalized_low_percent,
        "explanation": _coerce_explanation(explanation),
        "evidence": _coerce_evidence(evidence),
    }
    return validate_label_result(
        normalized,
        minimum_label_coverage_percent=minimum_label_coverage_percent,
        maximum_low_overlap_percent=maximum_low_overlap_percent,
        dimension_mode=dimension_mode,
    )


def normalize_display_title(row) -> str:
    show_title = _clean_whitespace(row.get("show_title", ""))
    title_value = _clean_whitespace(row.get("title", ""))

    title_parts = _collapse_repeated_title_parts(_split_title_parts(title_value))
    title_value = ": ".join(title_parts)

    if not show_title and not title_value:
        return "[Untitled]"
    if show_title and not title_value:
        return show_title
    if title_value and not show_title:
        return title_value

    if _normalize_compare_text(show_title) == _normalize_compare_text(title_value):
        return show_title

    if _normalize_compare_text(title_value).startswith(_normalize_compare_text(show_title)):
        return title_value

    return f"{show_title}: {title_value}"


def _get_item_quality_reason(row) -> str:
    raw_title = _clean_whitespace(row.get("title", ""))
    display_title = _clean_whitespace(row.get("display_title", "")) or normalize_display_title(row)
    reasons = []

    if display_title == "[Untitled]" or not re.search(r"[A-Za-z0-9]", display_title):
        reasons.append("missing title")

    if raw_title.endswith("...") or raw_title.endswith("…"):
        reasons.append("truncated title")

    if raw_title.endswith(":"):
        reasons.append("dangling title separator")

    if "\ufffd" in raw_title:
        reasons.append("invalid title characters")

    if _has_repeated_title_sequence(raw_title):
        reasons.append("duplicated title text")

    return "; ".join(dict.fromkeys(reasons))


def is_suspicious_title(row) -> bool:
    return bool(_get_item_quality_reason(row))


def format_prompt_item(row) -> str:
    display_title = _clean_whitespace(row.get("display_title", "")) or normalize_display_title(row)
    year_value = _format_year(row.get("year", ""))
    media_type = _clean_whitespace(row.get("media_type", "")).upper() or "UNKNOWN"
    genres = ", ".join(
        _split_tags(row.get("genre_tags", row.get("genres", "")), MAX_GENRE_TAGS)
    ) or "Unknown"
    directors = ", ".join(
        _split_tags(row.get("director_tags", row.get("directors", "")), MAX_DIRECTOR_NAMES)
    ) or "Unknown"
    actors = ", ".join(
        _split_tags(row.get("actor_tags", row.get("actors", "")), MAX_CAST_NAMES)
    ) or "Unknown"
    runtime = _format_runtime(row.get("duration", ""))
    rating = _clean_whitespace(row.get("rating", "")) or "Unknown"
    plot_hint_source = _clean_whitespace(row.get("summary", "")) or _clean_whitespace(row.get("episode_summary", ""))
    plot_hint = _trim_text(plot_hint_source, SUMMARY_HINT_CHARS) if plot_hint_source else "No synopsis available."

    username = _clean_whitespace(row.get("username", ""))
    metadata_line = f"  Dir: {directors} | Cast: {actors}"
    if username:
        metadata_line = f"  User: {username} | Dir: {directors} | Cast: {actors}"

    return (
        f"- {display_title} ({year_value}) | {media_type} | {genres}\n"
        f"{metadata_line}\n"
        f"  Runtime: {runtime} | Rating: {rating}\n"
        f"  Plot hint: {plot_hint}"
    )


def _ensure_metadata_columns(df: pd.DataFrame) -> pd.DataFrame:
    expected_cols = [
        "rating_key",
        "username",
        "title",
        "year",
        "media_type",
        "show_title",
        "rating",
        "summary",
        "duration",
        "genre_tags",
        "actor_tags",
        "director_tags",
        "watched_at",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    return df


def _order_dataframe(df: pd.DataFrame, key_column: str, requested_keys: list, secondary_desc_column: str | None = None) -> pd.DataFrame:
    if df.empty or key_column not in df.columns:
        return df

    order_map = {key: index for index, key in enumerate(requested_keys)}
    ordered = df.copy()
    ordered["_request_order"] = ordered[key_column].map(order_map).fillna(len(order_map)).astype(int)

    sort_columns = ["_request_order"]
    ascending = [True]
    if secondary_desc_column and secondary_desc_column in ordered.columns:
        sort_columns.append(secondary_desc_column)
        ascending.append(False)

    ordered = ordered.sort_values(sort_columns, ascending=ascending, na_position="last")
    return ordered.drop(columns=["_request_order"])


def prepare_dimension_items(
    df: pd.DataFrame,
    min_valid_items: int = MIN_VALID_ITEMS,
    dimension_mode: str = "media",
) -> dict:
    if df is None or df.empty:
        empty = pd.DataFrame(columns=["display_title", "item_quality_reason", "is_valid_item"])
        return {
            "all_items": empty,
            "valid_items": empty.copy(),
            "flagged_items": empty.copy(),
            "min_valid_items": min_valid_items,
        }

    prepared = _ensure_metadata_columns(df.copy()).reset_index(drop=True)
    prepared["display_title"] = prepared.apply(normalize_display_title, axis=1)
    prepared["item_quality_reason"] = prepared.apply(_get_item_quality_reason, axis=1)
    prepared["_dedupe_key"] = prepared.apply(
        lambda row: f"{_normalize_compare_text(row['display_title'])}|{_format_year(row.get('year', ''))}",
        axis=1,
    )

    if dimension_mode != "user":
        duplicate_mask = prepared.duplicated(subset=["_dedupe_key"], keep="first")
        prepared.loc[
            duplicate_mask & prepared["item_quality_reason"].eq(""),
            "item_quality_reason",
        ] = "duplicate title/year in sample"

    prepared["is_valid_item"] = prepared["item_quality_reason"].eq("")
    valid_items = prepared[prepared["is_valid_item"]].copy()
    flagged_items = prepared[~prepared["is_valid_item"]].copy()

    return {
        "all_items": prepared.drop(columns=["_dedupe_key"]),
        "valid_items": valid_items.drop(columns=["_dedupe_key"]),
        "flagged_items": flagged_items.drop(columns=["_dedupe_key"]),
        "min_valid_items": min_valid_items,
    }


def _format_item_block(items_df: pd.DataFrame, empty_text: str) -> str:
    if items_df is None or items_df.empty:
        return f"- {empty_text}"
    return "\n".join(format_prompt_item(row) for _, row in items_df.iterrows())


def _select_prompt_rows(
    items_df: pd.DataFrame,
    max_items: int,
    dimension_mode: str,
) -> pd.DataFrame:
    if items_df is None or items_df.empty:
        return items_df

    if dimension_mode != "user" or "username" not in items_df.columns:
        return items_df.head(max_items)

    working = items_df.copy()
    working["username"] = working["username"].map(_clean_whitespace)
    working["_sample_dedupe_key"] = working.apply(
        lambda row: (
            f"{_clean_whitespace(row.get('username', ''))}|"
            f"{_normalize_compare_text(row.get('display_title', ''))}|"
            f"{_format_year(row.get('year', ''))}"
        ),
        axis=1,
    )
    working = working.drop_duplicates(subset=["_sample_dedupe_key"], keep="first").drop(
        columns=["_sample_dedupe_key"]
    )
    grouped_rows = []
    user_groups = []
    for username, group in working.groupby("username", sort=False):
        if not username:
            continue
        user_groups.append((username, group.reset_index(drop=True)))

    if not user_groups:
        return working.head(max_items)

    selected_rows = []
    per_user_counts = {username: 0 for username, _ in user_groups}
    while len(selected_rows) < max_items:
        advanced = False
        for username, group in user_groups:
            if len(selected_rows) >= max_items:
                break
            idx = per_user_counts[username]
            if idx >= len(group) or idx >= MAX_ITEMS_PER_USER_IN_PROMPT:
                continue
            selected_rows.append(group.iloc[idx])
            per_user_counts[username] += 1
            advanced = True
        if not advanced:
            break

    if not selected_rows:
        return working.head(max_items)
    return pd.DataFrame(selected_rows).reset_index(drop=True)


def _get_dimension_scope_text(dimension_mode: str) -> str:
    if dimension_mode == "user":
        return (
            "USER preference dimension. HIGH and LOW items are representative watches from users whose "
            "user embedding values are highest or lowest on this dimension. Label the inferred viewer taste, "
            "preference, affinity, or tendency represented by the HIGH examples compared with the LOW examples. "
            "Do not label this as a direct title trait."
        )
    return (
        "MEDIA/title dimension. HIGH and LOW items are representative titles whose media embedding values are "
        "highest or lowest on this dimension. Label the content/title trait represented by the HIGH examples "
        "compared with the LOW examples."
    )


def _get_dimension_guidance_text(dimension_mode: str) -> str:
    if dimension_mode == "user":
        return (
            "Infer a taste or preference axis. Favor labels that describe what kinds of titles these users "
            "gravitate toward, such as genre/tone/era/franchise or creator-driven preferences. The label must "
            "make the viewer-preference perspective explicit, for example preference for, affinity for, taste "
            "for, tendency toward, interest in, or viewer affinity for. Do not label this as a single plot "
            "synopsis unless the same item-side pattern clearly repeats across users."
        )
    return (
        "Infer an item-side semantic separator. Favor labels that distinguish the high-value titles from the "
        "low-value titles based on concrete shared characteristics."
    )


def _get_label_style_guidance_text(dimension_mode: str) -> str:
    if dimension_mode == "user":
        return (
            '- Good USER labels are compact evidence-derived preference phrases, no more than 8 words, such as '
            '"preference for workplace comedy", "affinity for legal dramas", "taste for music performance '
            'stories", or "viewer affinity for relationship-driven stories".\n'
            "- Do not return plain title traits like \"workplace comedy\", \"medical drama\", or "
            '"action spectacle" for USER dimensions.'
        )
    return (
        '- Good MEDIA labels are compact evidence-derived noun phrases, no more than 8 words, such as '
        '"workplace comedy", "legal drama", "music performance stories", or "action spectacle".'
    )


def _resolve_dimension_mode(dimension: int, dimension_mode: str | None = None) -> str:
    cleaned_mode = _clean_whitespace(dimension_mode).lower()
    if cleaned_mode in {"media", "user"}:
        return cleaned_mode
    return get_dimension_mode(dimension)


def _format_review_context(
    existing_label: str | None = None,
    existing_display_label: str | None = None,
    existing_label_type: str | None = None,
) -> str:
    if not any(
        _clean_whitespace(value)
        for value in (existing_label, existing_display_label, existing_label_type)
    ):
        return ""

    return f"""
Review context:
Existing label: {_clean_whitespace(existing_label)}
Existing display label: {_clean_whitespace(existing_display_label)}
Existing label type: {_clean_whitespace(existing_label_type)}

Review instructions:
- Re-evaluate the existing label using only the current HIGH/LOW evidence.
- The HIGH/LOW examples are the source of truth; treat the existing label only as governance context.
- Do not preserve the existing wording unless the evidence independently supports it.
- UNCLEAR / MIXED SIGNAL remains a valid outcome.
- Do not force a replacement merely because this row is in review mode.
""".strip()


def build_dimension_prompt(
    dimension: int,
    positive_df: pd.DataFrame,
    negative_df: pd.DataFrame | None = None,
    dimension_mode: str | None = None,
    min_valid_items: int = MIN_VALID_ITEMS,
    minimum_label_coverage_percent: int = MINIMUM_LABEL_COVERAGE_PERCENT,
    maximum_low_overlap_percent: int = MAXIMUM_LOW_OVERLAP_PERCENT,
    existing_label: str | None = None,
    existing_display_label: str | None = None,
    existing_label_type: str | None = None,
) -> dict:
    dimension_mode = _resolve_dimension_mode(dimension, dimension_mode)
    positive_bundle = prepare_dimension_items(
        positive_df,
        min_valid_items=min_valid_items,
        dimension_mode=dimension_mode,
    )
    negative_bundle = prepare_dimension_items(
        negative_df if negative_df is not None else pd.DataFrame(),
        min_valid_items=0,
        dimension_mode=dimension_mode,
    )

    positive_items = _select_prompt_rows(
        positive_bundle["valid_items"],
        DEFAULT_TOP_POSITIVE_ITEMS,
        dimension_mode,
    )
    negative_items = _select_prompt_rows(
        negative_bundle["valid_items"],
        DEFAULT_TOP_NEGATIVE_ITEMS,
        dimension_mode,
    )

    skipped_reason = ""
    total_positive = len(positive_bundle["all_items"])
    valid_positive = len(positive_bundle["valid_items"])
    flagged_positive = len(positive_bundle["flagged_items"])

    if valid_positive < min_valid_items:
        skipped_reason = (
            f"Only {valid_positive} valid HIGH items remain after preprocessing "
            f"(minimum {min_valid_items})."
        )
    elif total_positive and flagged_positive > valid_positive:
        skipped_reason = "Malformed or duplicate HIGH items dominate the dimension sample."

    prompt_text = USER_PROMPT_TEMPLATE.format(
        dimension=dimension,
        dimension_scope=_get_dimension_scope_text(dimension_mode),
        dimension_specific_guidance=_get_dimension_guidance_text(dimension_mode),
        label_style_guidance=_get_label_style_guidance_text(dimension_mode),
        review_context=_format_review_context(
            existing_label=existing_label,
            existing_display_label=existing_display_label,
            existing_label_type=existing_label_type,
        ),
        min_valid_items=min_valid_items,
        minimum_label_coverage_percent=minimum_label_coverage_percent,
        maximum_low_overlap_percent=maximum_low_overlap_percent,
        high_item_count=len(positive_items),
        low_item_count=len(negative_items),
        top_positive_block=_format_item_block(positive_items, "No valid high items available."),
        top_negative_block=_format_item_block(negative_items, "No valid low items available."),
    )

    return {
        "prompt_text": prompt_text,
        "summary": generate_summary_text(positive_bundle["valid_items"], dimension, dimension_mode=dimension_mode),
        "positive_items": positive_items,
        "negative_items": negative_items,
        "valid_positive_count": valid_positive,
        "valid_negative_count": len(negative_bundle["valid_items"]),
        "minimum_label_coverage_percent": minimum_label_coverage_percent,
        "maximum_low_overlap_percent": maximum_low_overlap_percent,
        "flagged_item_count": flagged_positive + len(negative_bundle["flagged_items"]),
        "skipped_reason": skipped_reason,
    }


def generate_summary_text(df: pd.DataFrame, dimension: int, dimension_mode: str = "media") -> str:
    dimension_mode = _resolve_dimension_mode(dimension, dimension_mode)
    bundle = prepare_dimension_items(df, min_valid_items=0, dimension_mode=dimension_mode)
    valid_items = _select_prompt_rows(bundle["valid_items"], DEFAULT_TOP_POSITIVE_ITEMS, dimension_mode)
    summary_target = "watched items" if dimension_mode == "user" else "items"
    lines = [f"Top positive {summary_target} for embedding dimension {dimension}:"]
    if valid_items.empty:
        lines.append("- No valid items available.")
    else:
        lines.extend(format_prompt_item(row) for _, row in valid_items.iterrows())
    return "\n".join(lines)


def _build_user_prompt(
    dimension: int,
    top_positive_block: str,
    top_negative_block: str,
    dimension_mode: str | None = None,
    min_valid_items: int = MIN_VALID_ITEMS,
    minimum_label_coverage_percent: int = MINIMUM_LABEL_COVERAGE_PERCENT,
    maximum_low_overlap_percent: int = MAXIMUM_LOW_OVERLAP_PERCENT,
    high_item_count: int = DEFAULT_TOP_POSITIVE_ITEMS,
    low_item_count: int = DEFAULT_TOP_NEGATIVE_ITEMS,
    existing_label: str | None = None,
    existing_display_label: str | None = None,
    existing_label_type: str | None = None,
) -> str:
    dimension_mode = _resolve_dimension_mode(dimension, dimension_mode)
    return USER_PROMPT_TEMPLATE.format(
        dimension=dimension,
        dimension_scope=_get_dimension_scope_text(dimension_mode),
        dimension_specific_guidance=_get_dimension_guidance_text(dimension_mode),
        label_style_guidance=_get_label_style_guidance_text(dimension_mode),
        review_context=_format_review_context(
            existing_label=existing_label,
            existing_display_label=existing_display_label,
            existing_label_type=existing_label_type,
        ),
        min_valid_items=min_valid_items,
        minimum_label_coverage_percent=minimum_label_coverage_percent,
        maximum_low_overlap_percent=maximum_low_overlap_percent,
        high_item_count=high_item_count,
        low_item_count=low_item_count,
        top_positive_block=top_positive_block,
        top_negative_block=top_negative_block,
    )


def _extract_label_result_from_response(
    response_text: str,
    minimum_label_coverage_percent: int = MINIMUM_LABEL_COVERAGE_PERCENT,
    maximum_low_overlap_percent: int = MAXIMUM_LOW_OVERLAP_PERCENT,
    dimension_mode: str = "media",
) -> dict:
    raw = (response_text or "").strip()
    if not raw:
        raise ValueError("LLM returned an empty response")

    candidates = [raw]
    json_match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if json_match:
        candidates.insert(0, json_match.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except Exception:
            continue

        if isinstance(data, dict) and "label" in data:
            return _normalize_label_result(
                data.get("label", ""),
                data.get("explanation", ""),
                data.get("evidence", []),
                coverage_high_count=data.get("coverage_high_count"),
                coverage_high_total=data.get("coverage_high_total"),
                coverage_high_percent=data.get("coverage_high_percent"),
                coverage_low_overlap_count=data.get("coverage_low_overlap_count"),
                coverage_low_total=data.get("coverage_low_total"),
                coverage_low_overlap_percent=data.get("coverage_low_overlap_percent", data.get("coverage_low_percent")),
                label_confidence=data.get("label_confidence", data.get("confidence")),
                label_type=data.get("proposed_label_type", data.get("label_type")),
                minimum_label_coverage_percent=minimum_label_coverage_percent,
                maximum_low_overlap_percent=maximum_low_overlap_percent,
                dimension_mode=dimension_mode,
            )

    first_line = raw.splitlines()[0]
    return _normalize_label_result(
        first_line,
        "",
        [],
        minimum_label_coverage_percent=minimum_label_coverage_percent,
        maximum_low_overlap_percent=maximum_low_overlap_percent,
        dimension_mode=dimension_mode,
    )


def _extract_label_from_response(response_text: str) -> str:
    return _extract_label_result_from_response(response_text)["label"]


def _call_openai_for_label_result(prompt_text: str, model: str, dimension_mode: str = "media") -> dict:
    client = openai.OpenAI(api_key=get_setting_value("openai.api_key"))
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        max_tokens=420,
        temperature=0.1,
    )
    content = response.choices[0].message.content or ""
    return _extract_label_result_from_response(content, dimension_mode=dimension_mode)


def _list_ollama_models() -> list[str]:
    response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=30)
    response.raise_for_status()
    data = response.json()
    models = []
    for item in data.get("models", []):
        name = str(item.get("name") or item.get("model") or "").strip()
        if name:
            models.append(name)
    return models


def _resolve_ollama_model_name(model: str) -> str:
    requested = str(model or "").strip()
    if not requested:
        raise ValueError("No Ollama model name provided")

    installed = _list_ollama_models()
    if requested in installed:
        return requested

    if ":" not in requested:
        prefix_matches = sorted(name for name in installed if name.startswith(f"{requested}:"))
        if len(prefix_matches) == 1:
            return prefix_matches[0]
        if len(prefix_matches) > 1:
            match_list = ", ".join(prefix_matches)
            raise ValueError(
                f"Ollama model '{requested}' is ambiguous. Use one of: {match_list}"
            )

    match_list = ", ".join(installed[:12]) if installed else "none"
    raise ValueError(
        f"Ollama model '{requested}' is not installed on {OLLAMA_HOST}. "
        f"Available models: {match_list}"
    )


def _call_ollama_for_label_result(prompt_text: str, model: str, dimension_mode: str = "media") -> dict:
    resolved_model = _resolve_ollama_model_name(model)
    payload = {
        "model": resolved_model,
        "system": SYSTEM_PROMPT,
        "prompt": prompt_text,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
        },
    }
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json=payload,
        timeout=OLLAMA_TIMEOUT_S,
    )
    if response.status_code >= 400:
        try:
            error_message = response.json().get("error", response.text)
        except Exception:
            error_message = response.text
        raise RuntimeError(
            f"Ollama generate failed for model '{resolved_model}' at {OLLAMA_HOST}: "
            f"{response.status_code} {error_message}"
        )
    data = response.json()
    return _extract_label_result_from_response(data.get("response", ""), dimension_mode=dimension_mode)


def call_llm_for_label_result(
    prompt_text: str,
    provider: str | None = None,
    model: str | None = None,
    dimension_mode: str = "media",
    max_retries: int = 3,
    retry_delay_s: float = 1.0,
) -> dict:
    resolved_provider, resolved_model = resolve_label_backend(provider, model)
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            if resolved_provider == "openai":
                return _call_openai_for_label_result(prompt_text, resolved_model, dimension_mode=dimension_mode)
            return _call_ollama_for_label_result(prompt_text, resolved_model, dimension_mode=dimension_mode)
        except Exception as exc:
            last_error = exc
            if attempt == max_retries:
                break
            time.sleep(retry_delay_s * attempt)

    error_detail = f": {last_error}" if last_error else ""
    raise RuntimeError(
        f"Failed to generate label via {resolved_provider}:{resolved_model}{error_detail}"
    ) from last_error


def call_llm_for_label(
    prompt_text: str,
    provider: str | None = None,
    model: str | None = None,
    dimension_mode: str = "media",
    max_retries: int = 3,
    retry_delay_s: float = 1.0,
) -> str:
    return call_llm_for_label_result(
        prompt_text,
        provider=provider,
        model=model,
        dimension_mode=dimension_mode,
        max_retries=max_retries,
        retry_delay_s=retry_delay_s,
    )["label"]


def call_gpt_for_label(
    prompt_text,
    provider: str | None = None,
    model: str | None = None,
    dimension_mode: str = "media",
):
    return call_llm_for_label(
        prompt_text,
        provider=provider,
        model=model,
        dimension_mode=dimension_mode,
    )


def insert_label(dimension, label):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO embedding_labels (dimension, label, created_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (dimension)
        DO UPDATE SET label = EXCLUDED.label, created_at = EXCLUDED.created_at
        """,
        (dimension, label, datetime.utcnow())
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Saved label '{label}' for dimension {dimension}")


def get_dimension_mode(dimension: int) -> str:
    if 0 <= dimension < EMBEDDING_SIDE_DIMENSIONS:
        return "media"
    if EMBEDDING_SIDE_DIMENSIONS <= dimension < COMBINED_EMBEDDING_DIMENSIONS:
        return "user"
    raise ValueError(
        f"Dimension {dimension} is outside the combined embedding range "
        f"0-{COMBINED_EMBEDDING_DIMENSIONS - 1}"
    )


def get_media_embedding_index(dimension: int) -> int:
    if get_dimension_mode(dimension) != "media":
        raise ValueError(f"Media dimension {dimension} is outside the media range")
    return dimension


def get_user_embedding_index(dimension: int) -> int:
    if get_dimension_mode(dimension) != "user":
        raise ValueError(f"User dimension {dimension} is outside the user range")
    return dimension - EMBEDDING_SIDE_DIMENSIONS


def _get_ranked_embedding_ids(
    table_name: str,
    id_column: str,
    embedding_index: int,
    top_n: int = DEFAULT_FETCH_ITEMS,
    ascending: bool = False,
) -> list:
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(f"SELECT {id_column}, embedding FROM {table_name}")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=[id_column, "embedding"])
    if df.empty:
        return []

    df["dimension_value"] = df["embedding"].apply(lambda value: float(value[embedding_index]))
    ranked = df.nsmallest(top_n, "dimension_value") if ascending else df.nlargest(top_n, "dimension_value")
    return ranked[id_column].tolist()


def get_ranked_media_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS, ascending: bool = False):
    return _get_ranked_embedding_ids(
        "media_embeddings",
        "rating_key",
        get_media_embedding_index(dimension),
        top_n=top_n,
        ascending=ascending,
    )


def get_top_media_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS):
    return get_ranked_media_for_dimension(dimension, top_n=top_n, ascending=False)


def get_bottom_media_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS):
    return get_ranked_media_for_dimension(dimension, top_n=top_n, ascending=True)


def get_ranked_users_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS, ascending: bool = False):
    return _get_ranked_embedding_ids(
        "user_embeddings",
        "username",
        get_user_embedding_index(dimension),
        top_n=top_n,
        ascending=ascending,
    )


def get_top_users_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS):
    return get_ranked_users_for_dimension(dimension, top_n=top_n, ascending=False)


def get_bottom_users_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS):
    return get_ranked_users_for_dimension(dimension, top_n=top_n, ascending=True)


def get_media_metadata(rating_keys):
    if isinstance(rating_keys, int):
        rating_keys = [rating_keys]
    rating_keys = list(rating_keys or [])
    if not rating_keys:
        return _ensure_metadata_columns(pd.DataFrame())

    conn = connect_db()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                rating_key,
                title,
                year,
                media_type,
                show_title,
                rating,
                summary,
                duration,
                COALESCE(genres, '') AS genre_tags,
                COALESCE(actors, '') AS actor_tags,
                COALESCE(directors, '') AS director_tags
            FROM media_enriched_v
            WHERE rating_key = ANY(%s)
            """,
            (rating_keys,),
        )
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
    except Exception:
        conn.rollback()
        cur.execute(
            """
            SELECT
                m.rating_key,
                m.title,
                m.year,
                m.media_type,
                m.show_title,
                m.rating,
                COALESCE(NULLIF(m.summary, ''), m.episode_summary, '') AS summary,
                m.duration,
                COALESCE(g.genre_tags, '') AS genre_tags,
                COALESCE(a.actor_tags, '') AS actor_tags,
                COALESCE(d.director_tags, '') AS director_tags
            FROM library m
            LEFT JOIN (
                SELECT mg.media_id, STRING_AGG(g.name, ', ') AS genre_tags
                FROM media_genres mg
                JOIN genres g ON mg.genre_id = g.id
                GROUP BY mg.media_id
            ) g ON g.media_id = m.rating_key
            LEFT JOIN (
                SELECT ma.media_id, STRING_AGG(a.name, ', ' ORDER BY ma.cast_order NULLS LAST, a.name) AS actor_tags
                FROM media_actors ma
                JOIN actors a ON ma.actor_id = a.id
                GROUP BY ma.media_id
            ) a ON a.media_id = m.rating_key
            LEFT JOIN (
                SELECT md.media_id, STRING_AGG(d.name, ', ') AS director_tags
                FROM media_directors md
                JOIN directors d ON md.director_id = d.id
                GROUP BY md.media_id
            ) d ON d.media_id = m.rating_key
            WHERE m.rating_key = ANY(%s)
            """,
            (rating_keys,),
        )
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]

    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=colnames)
    df = _ensure_metadata_columns(df)
    return _order_dataframe(df, "rating_key", rating_keys)


def get_user_watch_history(usernames):
    usernames = list(usernames or [])
    if not usernames:
        return _ensure_metadata_columns(pd.DataFrame())

    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            w.username,
            w.watched_at,
            m.rating_key,
            m.title,
            m.year,
            m.media_type,
            m.show_title,
            m.rating,
            COALESCE(NULLIF(m.summary, ''), m.episode_summary, '') AS summary,
            m.duration,
            COALESCE(g.genre_tags, '') AS genre_tags,
            COALESCE(a.actor_tags, '') AS actor_tags,
            COALESCE(d.director_tags, '') AS director_tags
        FROM watch_history w
        JOIN library m ON w.rating_key = m.rating_key
        LEFT JOIN (
            SELECT mg.media_id, STRING_AGG(g.name, ', ') AS genre_tags
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            GROUP BY mg.media_id
        ) g ON g.media_id = m.rating_key
        LEFT JOIN (
            SELECT ma.media_id, STRING_AGG(a.name, ', ' ORDER BY ma.cast_order NULLS LAST, a.name) AS actor_tags
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            GROUP BY ma.media_id
        ) a ON a.media_id = m.rating_key
        LEFT JOIN (
            SELECT md.media_id, STRING_AGG(d.name, ', ') AS director_tags
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            GROUP BY md.media_id
        ) d ON d.media_id = m.rating_key
        WHERE w.username = ANY(%s)
        """,
        (usernames,),
    )
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=colnames)
    df = _ensure_metadata_columns(df)
    return _order_dataframe(df, "username", usernames, secondary_desc_column="watched_at")
