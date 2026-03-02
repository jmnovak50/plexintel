import json
import os
import re
import time
from datetime import datetime

import openai
import pandas as pd
import psycopg2
import requests
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

MIN_VALID_ITEMS = 6
DEFAULT_TOP_POSITIVE_ITEMS = 6
DEFAULT_TOP_NEGATIVE_ITEMS = 4
DEFAULT_FETCH_ITEMS = 10
SUMMARY_HINT_CHARS = 140
MAX_GENRE_TAGS = 3
MAX_CAST_NAMES = 2
MAX_DIRECTOR_NAMES = 2
MAX_ITEMS_PER_USER_IN_PROMPT = 2
UNCLEAR_LABEL = "UNCLEAR / MIXED SIGNAL"


def _strip_inline_annotation(value: str) -> str:
    cleaned = str(value).strip().strip("\"'")
    if "(default:" in cleaned:
        cleaned = cleaned.split("(default:", 1)[0].strip()
    return cleaned


def _get_env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    cleaned = _strip_inline_annotation(value)
    return cleaned or default


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    cleaned = _strip_inline_annotation(value)
    if not cleaned:
        return default

    try:
        return int(cleaned.split()[0])
    except ValueError:
        print(f"⚠️ Invalid {name}={value!r}; using default {default}")
        return default


LABEL_PROVIDER = _get_env_str("LABEL_PROVIDER", "ollama").lower()
OPENAI_LABEL_MODEL = _get_env_str("OPENAI_LABEL_MODEL", _get_env_str("LABEL_MODEL", "gpt-4"))
OLLAMA_HOST = _get_env_str("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_LABEL_MODEL = _get_env_str("OLLAMA_LABEL_MODEL", _get_env_str("LABEL_MODEL", "gemma3"))
OLLAMA_TIMEOUT_S = _get_env_int("OLLAMA_TIMEOUT_S", 300)

SYSTEM_PROMPT = """
You label one embedding dimension for film and TV data.

Use repeated patterns across the item metadata first.
Use plot hints only as secondary support, never as the sole basis for the label.

For media dimensions, identify a concrete item-side separator.
For user dimensions, infer a viewing-preference or taste separator from the representative watches
associated with HIGH versus LOW users.

Prefer concrete separators such as:
- genre blend
- tone
- setting or era
- format or franchise pattern
- cast/director cohort
- runtime or rating pattern
- what HIGH items have that LOW items usually do not

Avoid abstract trope language unless it is clearly supported by multiple items.
Do not use labels like redemption, coming of age, relationships, secrets, truth, purpose,
humanity, moral ambiguity, family healing, or similar moral-arc language unless the pattern is
explicitly repeated across several items and is supported by metadata, not just synopsis wording.

If the items are noisy, heterogeneous, malformed, or do not support a clear separator, use:
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

Rules:
- Use metadata first; use plot hints only as tie-breakers.
- Prefer concrete labels over abstract themes.
- Label must be 8 words or fewer.
- Explanation must be exactly 1 sentence.
- Provide exactly 3 evidence bullets as short strings.
- Each evidence bullet must cite repeated patterns from the items, not vague themes.
- If LOW items are present, explain what separates HIGH from LOW.
- If fewer than {min_valid_items} valid HIGH items remain, output UNCLEAR / MIXED SIGNAL.
- Also output UNCLEAR / MIXED SIGNAL if:
  1. HIGH items split into unrelated clusters,
  2. malformed or truncated titles dominate,
  3. the pattern is driven mostly by synopsis text,
  4. HIGH vs LOW contrast is weak or contradictory.

Return ONLY this JSON shape:
{{
  "label": "short label or UNCLEAR / MIXED SIGNAL",
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


def connect_db():
    conn = psycopg2.connect(DB_URL)
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


def _normalize_label_result(label: str, explanation: str = "", evidence=None) -> dict:
    return {
        "label": _coerce_label(label),
        "explanation": _coerce_explanation(explanation),
        "evidence": _coerce_evidence(evidence),
    }


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


def prepare_dimension_items(df: pd.DataFrame, min_valid_items: int = MIN_VALID_ITEMS) -> dict:
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
            "embedding values are highest or lowest on this dimension."
        )
    return "MEDIA semantic dimension. HIGH and LOW items are media titles with the highest or lowest values on this dimension."


def _get_dimension_guidance_text(dimension_mode: str) -> str:
    if dimension_mode == "user":
        return (
            "Infer a taste or preference axis. Favor labels that describe what kinds of titles these users "
            "gravitate toward, such as genre/tone/era/franchise or creator-driven preferences. Do not label "
            "this as a single plot synopsis unless the same item-side pattern clearly repeats across users."
        )
    return (
        "Infer an item-side semantic separator. Favor labels that distinguish the high-value titles from the "
        "low-value titles based on concrete shared characteristics."
    )


def build_dimension_prompt(
    dimension: int,
    positive_df: pd.DataFrame,
    negative_df: pd.DataFrame | None = None,
    dimension_mode: str = "media",
    min_valid_items: int = MIN_VALID_ITEMS,
) -> dict:
    positive_bundle = prepare_dimension_items(positive_df, min_valid_items=min_valid_items)
    negative_bundle = prepare_dimension_items(negative_df if negative_df is not None else pd.DataFrame(), min_valid_items=0)

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
        min_valid_items=min_valid_items,
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
        "flagged_item_count": flagged_positive + len(negative_bundle["flagged_items"]),
        "skipped_reason": skipped_reason,
    }


def generate_summary_text(df: pd.DataFrame, dimension: int, dimension_mode: str = "media") -> str:
    bundle = prepare_dimension_items(df, min_valid_items=0)
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
    dimension_mode: str = "media",
    min_valid_items: int = MIN_VALID_ITEMS,
) -> str:
    return USER_PROMPT_TEMPLATE.format(
        dimension=dimension,
        dimension_scope=_get_dimension_scope_text(dimension_mode),
        dimension_specific_guidance=_get_dimension_guidance_text(dimension_mode),
        min_valid_items=min_valid_items,
        top_positive_block=top_positive_block,
        top_negative_block=top_negative_block,
    )


def _extract_label_result_from_response(response_text: str) -> dict:
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
            )

    first_line = raw.splitlines()[0]
    return _normalize_label_result(first_line, "", [])


def _extract_label_from_response(response_text: str) -> str:
    return _extract_label_result_from_response(response_text)["label"]


def _call_openai_for_label_result(prompt_text: str, model: str) -> dict:
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text},
        ],
        max_tokens=220,
        temperature=0.1,
    )
    content = response.choices[0].message.content or ""
    return _extract_label_result_from_response(content)


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


def _call_ollama_for_label_result(prompt_text: str, model: str) -> dict:
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
    return _extract_label_result_from_response(data.get("response", ""))


def call_llm_for_label_result(
    prompt_text: str,
    provider: str | None = None,
    model: str | None = None,
    max_retries: int = 3,
    retry_delay_s: float = 1.0,
) -> dict:
    resolved_provider, resolved_model = resolve_label_backend(provider, model)
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            if resolved_provider == "openai":
                return _call_openai_for_label_result(prompt_text, resolved_model)
            return _call_ollama_for_label_result(prompt_text, resolved_model)
        except Exception as exc:
            last_error = exc
            if attempt == max_retries:
                break
            time.sleep(retry_delay_s * attempt)

    raise RuntimeError(
        f"Failed to generate label via {resolved_provider}:{resolved_model}"
    ) from last_error


def call_llm_for_label(
    prompt_text: str,
    provider: str | None = None,
    model: str | None = None,
    max_retries: int = 3,
    retry_delay_s: float = 1.0,
) -> str:
    return call_llm_for_label_result(
        prompt_text,
        provider=provider,
        model=model,
        max_retries=max_retries,
        retry_delay_s=retry_delay_s,
    )["label"]


def call_gpt_for_label(prompt_text, provider: str | None = None, model: str | None = None):
    return call_llm_for_label(prompt_text, provider=provider, model=model)


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
    if dimension < 768:
        raise ValueError(f"Media dimension {dimension} is below the media offset")
    return _get_ranked_embedding_ids(
        "media_embeddings",
        "rating_key",
        dimension - 768,
        top_n=top_n,
        ascending=ascending,
    )


def get_top_media_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS):
    return get_ranked_media_for_dimension(dimension, top_n=top_n, ascending=False)


def get_bottom_media_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS):
    return get_ranked_media_for_dimension(dimension, top_n=top_n, ascending=True)


def get_ranked_users_for_dimension(dimension, top_n: int = DEFAULT_FETCH_ITEMS, ascending: bool = False):
    if dimension >= 768:
        raise ValueError(f"User dimension {dimension} is outside the user range")
    return _get_ranked_embedding_ids(
        "user_embeddings",
        "username",
        dimension,
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
                SELECT ma.media_id, STRING_AGG(a.name, ', ') AS actor_tags
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
            SELECT ma.media_id, STRING_AGG(a.name, ', ') AS actor_tags
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
