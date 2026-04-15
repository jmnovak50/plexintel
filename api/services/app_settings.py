from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOTENV_PATH = REPO_ROOT / ".env"


SETTINGS_TABLE = "public.app_settings"
ENV_SOURCE = "env_bootstrap"
ADMIN_SOURCE = "admin_ui"
CLEARED_SOURCE = "cleared"
DEFAULT_SOURCE = "default"
RUNTIME_ENV_SOURCE = "env"
OVERRIDE_SOURCE = "override"

SECTION_DEFINITIONS: tuple[dict[str, str], ...] = (
    {"key": "connectivity", "label": "Connectivity"},
    {"key": "public_api", "label": "Public API"},
    {"key": "mcp", "label": "MCP Server"},
    {"key": "llm_embeddings", "label": "LLM & Embeddings"},
    {"key": "training_scoring", "label": "Training & Scoring"},
    {"key": "advanced_labeling", "label": "Advanced Labeling"},
    {"key": "email_digests", "label": "Email & Digests"},
)


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    section: str
    label: str
    value_type: str
    default: Any = None
    env_aliases: tuple[str, ...] = ()
    secret: bool = False
    description: str = ""
    choices: tuple[str, ...] = ()
    minimum: float | int | None = None
    maximum: float | int | None = None


@dataclass(frozen=True)
class EffectiveSetting:
    definition: SettingDefinition
    value: Any
    raw_value: str | None
    source: str
    updated_at: datetime | None
    updated_by: str | None
    has_value: bool


def _setting(
    key: str,
    section: str,
    label: str,
    value_type: str,
    *,
    default: Any = None,
    env_aliases: Iterable[str] = (),
    secret: bool = False,
    description: str = "",
    choices: Iterable[str] = (),
    minimum: float | int | None = None,
    maximum: float | int | None = None,
) -> SettingDefinition:
    return SettingDefinition(
        key=key,
        section=section,
        label=label,
        value_type=value_type,
        default=default,
        env_aliases=tuple(env_aliases),
        secret=secret,
        description=description,
        choices=tuple(choices),
        minimum=minimum,
        maximum=maximum,
    )


SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    _setting(
        "tautulli.api_url",
        "connectivity",
        "Tautulli API URL",
        "string",
        env_aliases=("TAUTULLI_API_URL",),
        description="Full Tautulli API endpoint, usually ending in /api/v2.",
    ),
    _setting(
        "tautulli.api_key",
        "connectivity",
        "Tautulli API Key",
        "string",
        env_aliases=("TAUTULLI_API_KEY",),
        secret=True,
    ),
    _setting(
        "tautulli.base_url",
        "connectivity",
        "Tautulli Base URL",
        "string",
        env_aliases=("TAUTULLI_URL",),
        description="Base Tautulli URL used for poster proxy and cache calls.",
    ),
    _setting(
        "plex.client_id",
        "connectivity",
        "Plex Client ID",
        "string",
        env_aliases=("PLEX_CLIENT_ID",),
    ),
    _setting(
        "plex.product",
        "connectivity",
        "Plex Product Name",
        "string",
        default="PlexIntel",
        env_aliases=("PLEX_PRODUCT",),
    ),
    _setting(
        "plex.version",
        "connectivity",
        "Plex Version",
        "string",
        default="1.0",
        env_aliases=("PLEX_VERSION",),
    ),
    _setting(
        "plex.redirect_uri",
        "connectivity",
        "Plex Redirect URI",
        "string",
        default="http://localhost:8489/api/auth/redirect",
        env_aliases=("PLEX_REDIRECT_URI",),
    ),
    _setting(
        "public_api.api_key",
        "public_api",
        "Public API Key",
        "string",
        env_aliases=("PUBLIC_API_KEY",),
        secret=True,
    ),
    _setting(
        "mcp.enabled",
        "mcp",
        "Enable MCP Server",
        "boolean",
        default=False,
        env_aliases=("MCP_ENABLED",),
        description="Expose the read-only MCP endpoint at /mcp for trusted clients.",
    ),
    _setting(
        "mcp.server_name",
        "mcp",
        "MCP Server Name",
        "string",
        default="PlexIntel",
        env_aliases=("MCP_SERVER_NAME",),
        description="Server name reported during MCP initialize.",
    ),
    _setting(
        "mcp.api_key",
        "mcp",
        "MCP API Key",
        "string",
        env_aliases=("MCP_API_KEY",),
        secret=True,
        description="Bearer token required for all /mcp requests.",
    ),
    _setting(
        "mcp.allowed_origins",
        "mcp",
        "Allowed Origins",
        "string",
        env_aliases=("MCP_ALLOWED_ORIGINS",),
        description="Comma-separated list of browser Origin values allowed to call /mcp.",
    ),
    _setting(
        "mcp.instructions",
        "mcp",
        "MCP Instructions",
        "string",
        env_aliases=("MCP_INSTRUCTIONS",),
        description="Optional instructions returned by the MCP initialize response.",
    ),
    _setting(
        "labeling.provider",
        "llm_embeddings",
        "Label Provider",
        "string",
        default="ollama",
        env_aliases=("LABEL_PROVIDER",),
        choices=("openai", "ollama"),
    ),
    _setting(
        "labeling.openai_model",
        "llm_embeddings",
        "OpenAI Label Model",
        "string",
        default="gpt-4",
        env_aliases=("OPENAI_LABEL_MODEL", "LABEL_MODEL"),
    ),
    _setting(
        "labeling.ollama_model",
        "llm_embeddings",
        "Ollama Label Model",
        "string",
        default="gemma3",
        env_aliases=("OLLAMA_LABEL_MODEL", "LABEL_MODEL"),
    ),
    _setting(
        "openai.api_key",
        "llm_embeddings",
        "OpenAI API Key",
        "string",
        env_aliases=("OPENAI_API_KEY",),
        secret=True,
    ),
    _setting(
        "ollama.host",
        "llm_embeddings",
        "Ollama Host",
        "string",
        default="http://localhost:11434",
        env_aliases=("OLLAMA_HOST",),
    ),
    _setting(
        "ollama.timeout_s",
        "llm_embeddings",
        "Ollama Timeout (seconds)",
        "integer",
        default=300,
        env_aliases=("OLLAMA_TIMEOUT_S",),
        minimum=1,
    ),
    _setting(
        "ollama.threads",
        "llm_embeddings",
        "Ollama Threads",
        "integer",
        default=None,
        env_aliases=("OLLAMA_THREADS",),
        minimum=0,
    ),
    _setting(
        "ollama.embedding_model",
        "llm_embeddings",
        "Ollama Embedding Model",
        "string",
        default="embeddinggemma",
        env_aliases=("OLLAMA_MODEL",),
    ),
    _setting(
        "embeddings.batch_size",
        "llm_embeddings",
        "Embedding Batch Size",
        "integer",
        default=128,
        env_aliases=("EMBED_BATCH_SIZE",),
        minimum=1,
    ),
    _setting(
        "embeddings.enable_media",
        "llm_embeddings",
        "Embed New Media During Sync",
        "boolean",
        default=True,
        env_aliases=("ENABLE_EMBED_MEDIA",),
    ),
    _setting(
        "embeddings.enable_watches",
        "llm_embeddings",
        "Embed New Watches During Sync",
        "boolean",
        default=True,
        env_aliases=("ENABLE_EMBED_WATCHES",),
    ),
    _setting(
        "embeddings.log_titles",
        "llm_embeddings",
        "Log Embedded Titles",
        "boolean",
        default=True,
        env_aliases=("LOG_EMBED_TITLES",),
    ),
    _setting(
        "training.engagement_threshold",
        "training_scoring",
        "Training Engagement Threshold",
        "float",
        default=0.7,
        minimum=0.0,
        maximum=1.0,
    ),
    _setting(
        "training.feedback_bonus",
        "training_scoring",
        "Feedback Bonus",
        "float",
        default=0.1,
    ),
    _setting(
        "training.enable_feedback",
        "training_scoring",
        "Enable Feedback Injection",
        "boolean",
        default=True,
    ),
    _setting(
        "training.use_sample_weight",
        "training_scoring",
        "Use Sample Weights",
        "boolean",
        default=True,
    ),
    _setting(
        "training.interested_sample_weight",
        "training_scoring",
        "Interested Sample Weight",
        "float",
        default=0.75,
        minimum=0.0,
    ),
    _setting(
        "training.watched_like_sample_weight",
        "training_scoring",
        "Watched Like Sample Weight",
        "float",
        default=3.0,
        minimum=0.0,
    ),
    _setting(
        "training.negative_sample_weight",
        "training_scoring",
        "Negative Sample Weight",
        "float",
        default=5.0,
        minimum=0.0,
    ),
    _setting(
        "training.watch_embed_min_engagement",
        "training_scoring",
        "Watch Embedding Minimum Engagement",
        "float",
        default=0.5,
        env_aliases=("WATCH_EMBED_MIN_ENGAGEMENT",),
        minimum=0.0,
        maximum=1.0,
    ),
    _setting(
        "user_embeddings.engagement_threshold",
        "training_scoring",
        "User Embedding Engagement Threshold",
        "float",
        default=0.5,
        env_aliases=("ENGAGEMENT_THRESHOLD",),
        minimum=0.0,
        maximum=1.0,
    ),
    _setting(
        "scoring.watched_engagement_threshold",
        "training_scoring",
        "Scoring Watched Engagement Threshold",
        "float",
        default=0.5,
        env_aliases=("WATCHED_ENGAGEMENT_THRESHOLD",),
        minimum=0.0,
        maximum=1.0,
    ),
    _setting(
        "scoring.shap_prune_days",
        "training_scoring",
        "SHAP Prune Days",
        "integer",
        default=3,
        env_aliases=("SHAP_PRUNE_DAYS",),
        minimum=0,
    ),
    _setting(
        "scoring.shap_max_items",
        "training_scoring",
        "SHAP Max Items",
        "integer",
        default=100,
        env_aliases=("SHAP_MAX_ITEMS",),
        minimum=1,
    ),
    _setting(
        "scoring.shap_raw_min_dims",
        "training_scoring",
        "SHAP Raw Min Dimensions",
        "integer",
        default=5,
        env_aliases=("SHAP_RAW_MIN_DIMS",),
        minimum=0,
    ),
    _setting(
        "scoring.shap_raw_max_dims",
        "training_scoring",
        "SHAP Raw Max Dimensions",
        "integer",
        default=20,
        env_aliases=("SHAP_RAW_MAX_DIMS",),
        minimum=0,
    ),
    _setting(
        "scoring.shap_raw_cumabs_target",
        "training_scoring",
        "SHAP Raw Cumulative Abs Target",
        "float",
        default=0.9,
        env_aliases=("SHAP_RAW_CUMABS_TARGET",),
        minimum=0.0,
        maximum=1.0,
    ),
    _setting(
        "scoring.shap_agg_top_dims",
        "training_scoring",
        "SHAP Aggregate Top Dimensions",
        "integer",
        default=50,
        env_aliases=("SHAP_AGG_TOP_DIMS",),
        minimum=0,
    ),
    _setting(
        "labeling.min_valid_items",
        "advanced_labeling",
        "Minimum Valid Items",
        "integer",
        default=6,
        minimum=1,
    ),
    _setting(
        "labeling.default_top_positive_items",
        "advanced_labeling",
        "Default Positive Items",
        "integer",
        default=6,
        minimum=1,
    ),
    _setting(
        "labeling.default_top_negative_items",
        "advanced_labeling",
        "Default Negative Items",
        "integer",
        default=4,
        minimum=0,
    ),
    _setting(
        "labeling.default_fetch_items",
        "advanced_labeling",
        "Default Fetch Items",
        "integer",
        default=10,
        minimum=1,
    ),
    _setting(
        "labeling.summary_hint_chars",
        "advanced_labeling",
        "Summary Hint Characters",
        "integer",
        default=140,
        minimum=20,
    ),
    _setting(
        "labeling.max_genre_tags",
        "advanced_labeling",
        "Maximum Genre Tags",
        "integer",
        default=3,
        minimum=1,
    ),
    _setting(
        "labeling.max_cast_names",
        "advanced_labeling",
        "Maximum Cast Names",
        "integer",
        default=2,
        minimum=1,
    ),
    _setting(
        "labeling.max_director_names",
        "advanced_labeling",
        "Maximum Director Names",
        "integer",
        default=2,
        minimum=1,
    ),
    _setting(
        "labeling.max_items_per_user_in_prompt",
        "advanced_labeling",
        "Maximum Items Per User In Prompt",
        "integer",
        default=2,
        minimum=1,
    ),
    _setting(
        "smtp.server",
        "email_digests",
        "SMTP Server",
        "string",
        env_aliases=("SMTP_SERVER",),
        description="Host for the SMTP server.",
    ),
    _setting(
        "smtp.port",
        "email_digests",
        "SMTP Port",
        "integer",
        default=465,
        env_aliases=("SMTP_PORT",),
        description="Port for the SMTP server.",
        minimum=1,
        maximum=65535,
    ),
    _setting(
        "smtp.username",
        "email_digests",
        "SMTP Username",
        "string",
        env_aliases=("SMTP_USERNAME",),
        description="Username for the SMTP server.",
    ),
    _setting(
        "smtp.password",
        "email_digests",
        "SMTP Password",
        "string",
        env_aliases=("SMTP_PASSWORD",),
        secret=True,
        description="Password for the SMTP server.",
    ),
    _setting(
        "smtp.encryption",
        "email_digests",
        "Encryption",
        "string",
        default="ssl_tls",
        env_aliases=("SMTP_ENCRYPTION",),
        description="Send emails encrypted using SSL/TLS or TLS/STARTTLS.",
        choices=("none", "starttls", "ssl_tls"),
    ),
    _setting(
        "smtp.from_name",
        "email_digests",
        "From Name",
        "string",
        default="PlexIntel",
        env_aliases=("SMTP_FROM_NAME",),
        description="Display name in the From header.",
    ),
    _setting(
        "smtp.from_email",
        "email_digests",
        "From Email",
        "string",
        env_aliases=("SMTP_FROM_EMAIL",),
        description="Email address used in the From header.",
    ),
    _setting(
        "smtp.reply_to",
        "email_digests",
        "Reply-To",
        "string",
        env_aliases=("SMTP_REPLY_TO",),
        description="Optional Reply-To email address.",
    ),
    _setting(
        "digest.enabled",
        "email_digests",
        "Enable Digests",
        "boolean",
        default=False,
        env_aliases=("DIGEST_ENABLED",),
        description="Send recommendation digest emails on the configured schedule.",
    ),
    _setting(
        "digest.frequency",
        "email_digests",
        "Digest Frequency",
        "string",
        default="weekly",
        env_aliases=("DIGEST_FREQUENCY",),
        choices=("daily", "weekly"),
    ),
    _setting(
        "digest.weekly_day",
        "email_digests",
        "Weekly Send Day",
        "string",
        default="monday",
        env_aliases=("DIGEST_WEEKLY_DAY",),
        choices=("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
    ),
    _setting(
        "digest.send_time",
        "email_digests",
        "Send Time",
        "string",
        default="09:00",
        env_aliases=("DIGEST_SEND_TIME",),
        description="Local send time in 24-hour HH:MM format.",
    ),
    _setting(
        "digest.timezone",
        "email_digests",
        "Timezone",
        "string",
        default="America/Chicago",
        env_aliases=("DIGEST_TIMEZONE",),
        description="IANA timezone used to calculate the send schedule.",
    ),
    _setting(
        "digest.top_movies",
        "email_digests",
        "Top Movies",
        "integer",
        default=25,
        env_aliases=("DIGEST_TOP_MOVIES",),
        description="How many movie recommendations to include per user.",
        minimum=0,
    ),
    _setting(
        "digest.top_shows",
        "email_digests",
        "Top Shows",
        "integer",
        default=10,
        env_aliases=("DIGEST_TOP_SHOWS",),
        description="How many show recommendations to include per user.",
        minimum=0,
    ),
    _setting(
        "digest.base_url",
        "email_digests",
        "Digest Base URL",
        "string",
        default="http://localhost:8489",
        env_aliases=("DIGEST_BASE_URL",),
        description="Public PlexIntel URL used for links in digest emails.",
    ),
)

SETTINGS_BY_KEY = {definition.key: definition for definition in SETTING_DEFINITIONS}


class SettingsValidationError(ValueError):
    pass


def load_settings_env() -> None:
    load_dotenv(DEFAULT_DOTENV_PATH, override=False)


load_settings_env()


def ensure_settings_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SETTINGS_TABLE} (
                key text PRIMARY KEY,
                raw_value text,
                source text NOT NULL,
                updated_at timestamp with time zone NOT NULL DEFAULT now(),
                updated_by text
            )
            """
        )


def _strip_inline_annotation(value: str) -> str:
    cleaned = str(value).strip().strip("\"'")
    if "(default:" in cleaned:
        cleaned = cleaned.split("(default:", 1)[0].strip()
    return cleaned


def _normalize_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SettingsValidationError("must be a valid http or https URL")
    return value.rstrip("/")


def _normalize_email(value: str) -> str:
    display_name, email_address = parseaddr(value)
    normalized = (email_address or "").strip()
    if display_name:
        raise SettingsValidationError("must be a plain email address")
    if not normalized or "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise SettingsValidationError("must be a valid email address")
    local_part, _, domain = normalized.rpartition("@")
    if "." not in domain or not local_part or not domain:
        raise SettingsValidationError("must be a valid email address")
    return normalized


def _normalize_time_of_day(value: str) -> str:
    cleaned = value.strip()
    if not re.fullmatch(r"\d{2}:\d{2}", cleaned):
        raise SettingsValidationError("must use HH:MM 24-hour time")
    hours, minutes = cleaned.split(":")
    if int(hours) > 23 or int(minutes) > 59:
        raise SettingsValidationError("must use HH:MM 24-hour time")
    return cleaned


def _normalize_timezone(value: str) -> str:
    cleaned = value.strip()
    try:
        ZoneInfo(cleaned)
    except ZoneInfoNotFoundError as exc:
        raise SettingsValidationError("must be a valid IANA timezone") from exc
    return cleaned


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    cleaned = _strip_inline_annotation(value).lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    raise SettingsValidationError("must be a boolean value")


def parse_value(definition: SettingDefinition, value: Any) -> Any:
    if value is None:
        return None

    if definition.value_type == "string":
        parsed_value = _strip_inline_annotation(value)
        if not parsed_value:
            return None
        if definition.key.endswith("_url") or definition.key in {
            "tautulli.api_url",
            "tautulli.base_url",
            "ollama.host",
            "plex.redirect_uri",
            "digest.base_url",
        }:
            parsed_value = _normalize_url(parsed_value)
        elif definition.key in {"smtp.from_email", "smtp.reply_to"}:
            parsed_value = _normalize_email(parsed_value)
        elif definition.key == "digest.send_time":
            parsed_value = _normalize_time_of_day(parsed_value)
        elif definition.key == "digest.timezone":
            parsed_value = _normalize_timezone(parsed_value)
    elif definition.value_type == "integer":
        cleaned = _strip_inline_annotation(value)
        if cleaned == "":
            return None
        try:
            parsed_value = int(cleaned.split()[0])
        except ValueError as exc:
            raise SettingsValidationError("must be an integer") from exc
    elif definition.value_type == "float":
        cleaned = _strip_inline_annotation(value)
        if cleaned == "":
            return None
        try:
            parsed_value = float(cleaned.split()[0])
        except ValueError as exc:
            raise SettingsValidationError("must be a number") from exc
    elif definition.value_type == "boolean":
        parsed_value = _parse_bool(value)
    else:
        raise SettingsValidationError(f"unsupported setting type: {definition.value_type}")

    if parsed_value is not None and definition.choices and str(parsed_value) not in definition.choices:
        choices = ", ".join(definition.choices)
        raise SettingsValidationError(f"must be one of: {choices}")
    if parsed_value is not None and definition.minimum is not None and parsed_value < definition.minimum:
        raise SettingsValidationError(f"must be >= {definition.minimum}")
    if parsed_value is not None and definition.maximum is not None and parsed_value > definition.maximum:
        raise SettingsValidationError(f"must be <= {definition.maximum}")
    return parsed_value


def format_raw_value(definition: SettingDefinition, value: Any) -> str | None:
    if value is None:
        return None
    if definition.value_type == "boolean":
        return "true" if value else "false"
    if definition.value_type == "float":
        return f"{float(value):g}"
    return str(value)


def mask_secret(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    visible = raw_value[-4:] if len(raw_value) > 4 else raw_value
    masked_prefix = "*" * max(4, len(raw_value) - len(visible))
    return f"{masked_prefix}{visible}"


def get_setting_definition(key: str) -> SettingDefinition:
    try:
        return SETTINGS_BY_KEY[key]
    except KeyError as exc:
        raise SettingsValidationError(f"unknown setting: {key}") from exc


def _read_env_value(definition: SettingDefinition) -> tuple[Any, str | None]:
    for env_name in definition.env_aliases:
        env_value = os.getenv(env_name)
        if env_value is None or str(env_value).strip() == "":
            continue
        try:
            parsed = parse_value(definition, env_value)
        except SettingsValidationError:
            continue
        return parsed, env_name
    return None, None


def _fetch_setting_rows(keys: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
    try:
        conn = connect_db(cursor_factory=RealDictCursor)
    except Exception:
        return {}

    try:
        with conn.cursor() as cur:
            if keys:
                cur.execute(
                    f"""
                    SELECT key, raw_value, source, updated_at, updated_by
                    FROM {SETTINGS_TABLE}
                    WHERE key = ANY(%s)
                    """,
                    (list(keys),),
                )
            else:
                cur.execute(
                    f"""
                    SELECT key, raw_value, source, updated_at, updated_by
                    FROM {SETTINGS_TABLE}
                    """
                )
            rows = cur.fetchall()
    except Exception:
        return {}
    finally:
        conn.close()

    return {row["key"]: row for row in rows}


def bootstrap_settings_from_env(conn) -> None:
    ensure_settings_schema(conn)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT key FROM {SETTINGS_TABLE}")
        existing_keys = {row["key"] for row in cur.fetchall()}
        for definition in SETTING_DEFINITIONS:
            if definition.key in existing_keys:
                continue
            env_value, _env_name = _read_env_value(definition)
            if env_value is None:
                continue
            cur.execute(
                f"""
                INSERT INTO {SETTINGS_TABLE} (key, raw_value, source)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO NOTHING
                """,
                (definition.key, format_raw_value(definition, env_value), ENV_SOURCE),
            )
    conn.commit()


def ensure_settings_bootstrap() -> None:
    try:
        conn = connect_db()
    except Exception:
        return

    try:
        bootstrap_settings_from_env(conn)
    finally:
        conn.close()


def resolve_settings(
    *,
    keys: Iterable[str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, EffectiveSetting]:
    selected_definitions = (
        [get_setting_definition(key) for key in keys]
        if keys is not None
        else list(SETTING_DEFINITIONS)
    )
    rows = _fetch_setting_rows(definition.key for definition in selected_definitions)
    override_map = overrides or {}
    resolved: dict[str, EffectiveSetting] = {}

    for definition in selected_definitions:
        if definition.key in override_map:
            override_value = parse_value(definition, override_map[definition.key])
            resolved[definition.key] = EffectiveSetting(
                definition=definition,
                value=override_value,
                raw_value=format_raw_value(definition, override_value),
                source=OVERRIDE_SOURCE,
                updated_at=None,
                updated_by=None,
                has_value=override_value is not None,
            )
            continue

        row = rows.get(definition.key)
        if row:
            if row["raw_value"] is None:
                resolved_value = definition.default
                has_value = definition.default is not None
            else:
                resolved_value = parse_value(definition, row["raw_value"])
                has_value = resolved_value is not None
            resolved[definition.key] = EffectiveSetting(
                definition=definition,
                value=resolved_value,
                raw_value=row["raw_value"],
                source=row["source"],
                updated_at=row.get("updated_at"),
                updated_by=row.get("updated_by"),
                has_value=has_value,
            )
            continue

        env_value, _env_name = _read_env_value(definition)
        if env_value is not None:
            resolved[definition.key] = EffectiveSetting(
                definition=definition,
                value=env_value,
                raw_value=format_raw_value(definition, env_value),
                source=RUNTIME_ENV_SOURCE,
                updated_at=None,
                updated_by=None,
                has_value=True,
            )
            continue

        resolved[definition.key] = EffectiveSetting(
            definition=definition,
            value=definition.default,
            raw_value=format_raw_value(definition, definition.default),
            source=DEFAULT_SOURCE,
            updated_at=None,
            updated_by=None,
            has_value=definition.default is not None,
        )

    return resolved


def get_setting_value(key: str, *, default: Any = None, overrides: dict[str, Any] | None = None) -> Any:
    resolved = resolve_settings(keys=[key], overrides=overrides)
    value = resolved[key].value
    return default if value is None else value


def get_settings_payload() -> list[dict[str, Any]]:
    resolved = resolve_settings()
    sections_by_key = {section["key"]: {**section, "fields": []} for section in SECTION_DEFINITIONS}
    for definition in SETTING_DEFINITIONS:
        effective = resolved[definition.key]
        section = sections_by_key[definition.section]
        field_payload = {
            "key": definition.key,
            "label": definition.label,
            "description": definition.description,
            "type": definition.value_type,
            "secret": definition.secret,
            "default_value": None if definition.secret else definition.default,
            "source": effective.source,
            "updated_at": effective.updated_at,
            "updated_by": effective.updated_by,
            "has_value": effective.has_value,
            "value": None if definition.secret else effective.value,
            "masked_value": mask_secret(effective.raw_value) if definition.secret and effective.has_value else None,
            "choices": list(definition.choices),
            "minimum": definition.minimum,
            "maximum": definition.maximum,
        }
        section["fields"].append(field_payload)
    return [sections_by_key[section["key"]] for section in SECTION_DEFINITIONS]


def save_settings(*, updates: dict[str, Any], clear_keys: Iterable[str], updated_by: str | None) -> None:
    normalized_updates: dict[str, tuple[SettingDefinition, Any]] = {}
    for key, value in (updates or {}).items():
        definition = get_setting_definition(key)
        normalized_updates[key] = (definition, parse_value(definition, value))

    normalized_clears = [get_setting_definition(key).key for key in clear_keys or []]

    conn = connect_db()
    try:
        ensure_settings_schema(conn)
        with conn.cursor() as cur:
            for key in normalized_clears:
                cur.execute(
                    f"""
                    INSERT INTO {SETTINGS_TABLE} (key, raw_value, source, updated_at, updated_by)
                    VALUES (%s, NULL, %s, now(), %s)
                    ON CONFLICT (key) DO UPDATE SET
                        raw_value = NULL,
                        source = EXCLUDED.source,
                        updated_at = EXCLUDED.updated_at,
                        updated_by = EXCLUDED.updated_by
                    """,
                    (key, CLEARED_SOURCE, updated_by),
                )
            for key, (definition, value) in normalized_updates.items():
                cur.execute(
                    f"""
                    INSERT INTO {SETTINGS_TABLE} (key, raw_value, source, updated_at, updated_by)
                    VALUES (%s, %s, %s, now(), %s)
                    ON CONFLICT (key) DO UPDATE SET
                        raw_value = EXCLUDED.raw_value,
                        source = EXCLUDED.source,
                        updated_at = EXCLUDED.updated_at,
                        updated_by = EXCLUDED.updated_by
                    """,
                    (key, format_raw_value(definition, value), ADMIN_SOURCE, updated_by),
                )
        conn.commit()
    finally:
        conn.close()


def build_settings_overrides(updates: dict[str, Any] | None = None, clear_keys: Iterable[str] | None = None) -> dict[str, Any]:
    overrides = dict(updates or {})
    for key in clear_keys or []:
        overrides[key] = None
    return overrides


def test_tautulli_settings(*, updates: dict[str, Any] | None = None, clear_keys: Iterable[str] | None = None) -> dict[str, Any]:
    overrides = build_settings_overrides(updates, clear_keys)
    api_url = get_setting_value("tautulli.api_url", overrides=overrides)
    api_key = get_setting_value("tautulli.api_key", overrides=overrides)
    base_url = get_setting_value("tautulli.base_url", overrides=overrides)

    if not api_url or not api_key:
        raise SettingsValidationError("Tautulli API URL and API key are required")

    response = requests.get(
        api_url,
        params={"apikey": api_key, "cmd": "get_users"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("response", {}).get("data")
    user_count = len(data.get("users", [])) if isinstance(data, dict) else None

    return {
        "ok": True,
        "api_url": api_url,
        "base_url": base_url,
        "user_count": user_count,
    }


def test_ollama_settings(*, updates: dict[str, Any] | None = None, clear_keys: Iterable[str] | None = None) -> dict[str, Any]:
    overrides = build_settings_overrides(updates, clear_keys)
    host = get_setting_value("ollama.host", overrides=overrides)
    timeout_s = get_setting_value("ollama.timeout_s", overrides=overrides)
    label_model = get_setting_value("labeling.ollama_model", overrides=overrides)
    embedding_model = get_setting_value("ollama.embedding_model", overrides=overrides)

    if not host:
        raise SettingsValidationError("Ollama host is required")

    response = requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout_s or 30)
    response.raise_for_status()
    payload = response.json()
    model_names = sorted(
        model.get("name")
        for model in payload.get("models", [])
        if isinstance(model, dict) and model.get("name")
    )

    requested_models = [name for name in [label_model, embedding_model] if name]
    missing_models = [name for name in requested_models if name not in model_names]

    return {
        "ok": True,
        "host": host,
        "available_models": model_names,
        "missing_models": missing_models,
    }
