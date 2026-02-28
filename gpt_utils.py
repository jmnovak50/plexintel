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

SYSTEM_PROMPT = (
    "Label the shared semantic theme across media examples."
)

USER_PROMPT_TEMPLATE = """
Identify the strongest shared theme across these items.
Prefer tone, narrative pattern, setting, or motif over generic genres.
Use 2 to 8 words.
Return ONLY valid JSON:
{{"label": "short descriptive phrase"}}

Items:
{prompt_text}
"""

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


def _build_user_prompt(prompt_text: str) -> str:
    return USER_PROMPT_TEMPLATE.format(prompt_text=prompt_text)


def _coerce_label(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(label or "")).strip().strip("\"'")
    cleaned = cleaned.rstrip(".")
    if not cleaned:
        raise ValueError("Label response was empty")
    if len(cleaned) > 120:
        cleaned = cleaned[:120].rstrip()
    return cleaned


def _extract_label_from_response(response_text: str) -> str:
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
            if isinstance(data, dict) and "label" in data:
                return _coerce_label(data["label"])
        except Exception:
            continue

    # Fall back to plain-text output if the model ignored the JSON instruction.
    first_line = raw.splitlines()[0]
    return _coerce_label(first_line)


def _call_openai_for_label(prompt_text: str, model: str) -> str:
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(prompt_text)},
        ],
        max_tokens=80,
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    return _extract_label_from_response(content)


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


def _call_ollama_for_label(prompt_text: str, model: str) -> str:
    resolved_model = _resolve_ollama_model_name(model)
    payload = {
        "model": resolved_model,
        "system": SYSTEM_PROMPT,
        "prompt": _build_user_prompt(prompt_text),
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
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
    return _extract_label_from_response(data.get("response", ""))


def call_llm_for_label(
    prompt_text: str,
    provider: str | None = None,
    model: str | None = None,
    max_retries: int = 3,
    retry_delay_s: float = 1.0,
) -> str:
    resolved_provider, resolved_model = resolve_label_backend(provider, model)
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            if resolved_provider == "openai":
                return _call_openai_for_label(prompt_text, resolved_model)
            return _call_ollama_for_label(prompt_text, resolved_model)
        except Exception as exc:
            last_error = exc
            if attempt == max_retries:
                break
            time.sleep(retry_delay_s * attempt)

    raise RuntimeError(
        f"Failed to generate label via {resolved_provider}:{resolved_model}"
    ) from last_error


def call_gpt_for_label(prompt_text, provider: str | None = None, model: str | None = None):
    # Backward-compatible wrapper retained for existing scripts/imports.
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

def get_top_media_for_dimension(dimension, top_n=10):
    media_dim = dimension - 768
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT rating_key, embedding FROM media_embeddings")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=["rating_key", "embedding"])
    df[f"emb_{dimension}"] = df["embedding"].apply(lambda v: v[media_dim])
    top = df.sort_values(f"emb_{dimension}", ascending=False).head(top_n)
    return top["rating_key"].tolist()

def get_top_users_for_dimension(dimension, top_n=10):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT username, embedding FROM user_embeddings")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=["username", "embedding"])
    df[f"emb_{dimension}"] = df["embedding"].apply(lambda v: v[dimension])
    top = df.sort_values(f"emb_{dimension}", ascending=False).head(top_n)
    return top["username"].tolist()

def get_media_metadata(rating_keys):
    from psycopg2.extras import execute_values
    if isinstance(rating_keys, int):
        rating_keys = [rating_keys]

    conn = connect_db()
    cur = conn.cursor()
    sql = """
        SELECT
        m.rating_key,
        m.title,
        m.year,
        m.media_type,
        m.show_title,
        m.rating,
        m.summary,
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
    """
    cur.execute(sql, (rating_keys,))
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=colnames)
    expected_cols = ["title", "year", "media_type", "show_title", "rating", "summary", "genre_tags", "actor_tags", "director_tags"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    return df

def get_user_watch_history(usernames):
    conn = connect_db()
    cur = conn.cursor()
    sql = """
        SELECT
            w.username,
            m.rating_key,
            m.title,
            m.year,
            m.media_type,
            m.show_title,
            m.rating,
            m.summary,
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
        ORDER BY w.watched_at DESC NULLS LAST
    """
    cur.execute(sql, (usernames,))
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=colnames)
    expected_cols = ["title", "year", "media_type", "show_title", "rating", "summary", "genre_tags", "actor_tags", "director_tags"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""
    return df

def generate_summary_text(df, dimension):
    def _safe_str(value):
        if value is None or pd.isna(value):
            return ""
        return str(value)

    lines = [f"Top items for embedding dimension {dimension}:"]
    for _, row in df.head(6).iterrows():
        media_type = _safe_str(row.get("media_type", "")).strip().upper()
        media_type_label = f"[{media_type}]" if media_type else "[UNKNOWN]"

        show_title = _safe_str(row.get("show_title", "")).strip()
        title_value = _safe_str(row.get("title", "")).strip()
        year_value = _safe_str(row.get("year", "")).strip()

        base_title = f"{show_title}: {title_value}" if show_title else title_value
        title = f"{media_type_label} {base_title} ({year_value})"

        genre_tags = ", ".join(
            tag.strip() for tag in _safe_str(row.get("genre_tags", "")).split(",")[:3] if tag.strip()
        )
        title_line = f"- {title}"
        if genre_tags:
            title_line += f" | {genre_tags}"
        extras = []

        if pd.notna(row.get('director_tags')) and row['director_tags']:
            trimmed_directors = ", ".join(row['director_tags'].split(", ")[:2])
            extras.append(f"Director(s): {trimmed_directors}")

        if pd.notna(row.get('actor_tags')) and row['actor_tags']:
            trimmed_actors = ", ".join(row['actor_tags'].split(", ")[:2])
            extras.append(f"Actor(s): {trimmed_actors}")

        if pd.notna(row.get('rating')) and _safe_str(row.get('rating')).strip():
            extras.append(f"Rating: {row['rating']}")

        if extras:
            title_line += "\n  " + " | ".join(extras)

        if pd.notna(row.get('summary')) and row['summary']:
            summary_text = row['summary'][:220].strip()
            if len(row['summary']) > 220:
                summary_text += "..."
            title_line += f"\n  {summary_text}"

        lines.append(title_line + "\n")
    return "".join(lines)
