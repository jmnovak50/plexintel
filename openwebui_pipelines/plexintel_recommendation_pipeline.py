"""
title: PlexIntel Recommendation Pipeline
author: jmnovak
version: 0.1.2
requirements: requests
description: Deterministic PlexIntel recommendation, search, poster, and watch-history workflows for OpenWebUI Pipelines.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Generator, Iterator, Optional, Union

from pydantic import BaseModel, Field
import requests


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class PipelineHttpError(Exception):
    def __init__(
        self,
        *,
        endpoint: str,
        status_code: int | None = None,
        detail: str | None = None,
    ):
        super().__init__(detail or endpoint)
        self.endpoint = endpoint
        self.status_code = status_code
        self.detail = detail


class UserResolution:
    def __init__(
        self,
        username: str | None,
        friendly_name: str | None = None,
        candidates: list[dict[str, Any]] | None = None,
        reason: str | None = None,
    ):
        self.username = username
        self.friendly_name = friendly_name
        self.candidates = candidates
        self.reason = reason

    @property
    def ok(self) -> bool:
        return bool(self.username)


class Pipeline:
    class Valves(BaseModel):
        PLEXINTEL_BASE_URL: str = Field(
            default="http://192.168.1.9:8489",
            description="Base URL for PlexIntel, without a trailing slash.",
        )
        # OpenWebUI configuration (kept for backward compatibility)
        OPENWEBUI_BASE_URL: str = Field(
            default="http://localhost:3000",
            description="Base URL for OpenWebUI, without a trailing slash.",
        )
        OPENWEBUI_API_KEY: str = Field(
            default="",
            description="OpenWebUI API key for optional Gemma narration.",
        )
        # Ollama configuration for Gemma models
        OLLAMA_BASE_URL: str = Field(
            default="http://localhost:11434",
            description="Base URL for Ollama server, without a trailing slash.",
        )
        OLLAMA_MODEL: str = Field(
            default="gemma4:31b-cloud",
            description="Ollama model name for Gemma narration.",
        )
        ENABLE_GEMMA_NARRATION: bool = Field(
            default=True,
            description="Allow Gemma to add a short prose explanation after deterministic data is fetched.",
        )
        USER_ALIASES_JSON: str = Field(
            default="{}",
            description='JSON object mapping OpenWebUI email/name/id values to Plex usernames.',
        )
        DEFAULT_LIMIT: int = Field(default=8, ge=1)
        MAX_LIMIT: int = Field(default=20, ge=1)
        POSTER_WIDTH: int = Field(default=180, ge=1, le=1200)
        REQUEST_TIMEOUT_S: int = Field(default=30, ge=1)

    def __init__(self):
        self.id = "plexintel_recommendations"
        self.name = "PlexIntel Recommendations"
        self.type = "pipe"
        self.description = "Deterministic PlexIntel recommendation, search, poster, and watch-history workflows."
        self.version = "0.1.2"
        self.valves = self.Valves(
            PLEXINTEL_BASE_URL=os.getenv("PLEXINTEL_BASE_URL", "http://192.168.1.9:8489"),
            OPENWEBUI_BASE_URL=os.getenv("OPENWEBUI_BASE_URL", "http://localhost:3000"),
            OPENWEBUI_API_KEY=os.getenv("OPENWEBUI_API_KEY", ""),
            GEMMA_MODEL=os.getenv("GEMMA_MODEL", "gemma3"),
            ENABLE_GEMMA_NARRATION=_env_bool("ENABLE_GEMMA_NARRATION", True),
            USER_ALIASES_JSON=os.getenv("USER_ALIASES_JSON", "{}"),
            DEFAULT_LIMIT=_env_int("DEFAULT_LIMIT", 8),
            MAX_LIMIT=_env_int("MAX_LIMIT", 20),
            POSTER_WIDTH=_env_int("POSTER_WIDTH", 180),
            REQUEST_TIMEOUT_S=_env_int("REQUEST_TIMEOUT_S", 30),
        )

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        pass

    def pipe(
        self,
        user_message: str = "",
        model_id: str = "",
        messages: Optional[list[dict[str, Any]]] = None,
        body: Optional[dict[str, Any]] = None,
    ) -> Union[str, Generator, Iterator]:
        del model_id
        body = body or {}
        messages = messages or body.get("messages") or []
        prompt = (user_message or self._last_user_message(messages)).strip()

        if body.get("title"):
            return self._short_title(prompt)

        try:
            workflow = self._select_workflow(prompt)
            if workflow == "list_users":
                return self._handle_list_users()
            if workflow == "search":
                return self._handle_search(prompt)
            if workflow == "item_poster":
                return self._handle_item_poster(prompt)
            if workflow == "watch_history":
                return self._handle_watch_history(prompt, body)
            return self._handle_recommendations(prompt, body)
        except PipelineHttpError as exc:
            return self._render_http_error(exc)
        except Exception as exc:
            return (
                "## PlexIntel Pipeline Error\n\n"
                f"The deterministic pipeline failed before it could complete the workflow: `{exc}`"
            )

    def _last_user_message(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str):
                    return content
        return ""

    def _short_title(self, prompt: str) -> str:
        cleaned = re.sub(r"\s+", " ", prompt).strip()
        if not cleaned:
            return "PlexIntel"
        if re.search(r"\brecommend|recommendation|watch\b", cleaned, flags=re.I):
            return "PlexIntel recommendations"
        words = re.findall(r"[A-Za-z0-9']+", cleaned)[:6]
        return " ".join(words) or "PlexIntel"

    def _select_workflow(self, prompt: str) -> str:
        text = prompt.lower()
        if re.search(r"\b(list|show|who are|what are)\b.*\b(users|plex users)\b", text):
            return "list_users"
        if re.search(r"\b(watch history|watched|recently watched|viewing history)\b", text):
            return "watch_history"
        if "poster" in text and self._extract_rating_key(prompt) is not None:
            return "item_poster"
        if re.search(r"\b(search|find|look up)\b", text):
            return "search"
        if re.search(r"\bposter\s+(?:for|of)\b", text):
            return "item_poster"
        return "recommendations"

    def _plex_get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._http_json("GET", self._plexintel_url(path), params=params)

    def _plex_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._http_json("POST", self._plexintel_url(path), json_payload=payload)

    def _openwebui_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.valves.OPENWEBUI_API_KEY}",
            "Content-Type": "application/json",
        }
        return self._http_json(
            "POST",
            f"{self.valves.OPENWEBUI_BASE_URL.rstrip('/')}{path}",
            json_payload=payload,
            headers=headers,
        )

    def _ollama_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request to an Ollama server.

        The Ollama API is similar to OpenAI's chat endpoint but hosted locally.
        ``path`` should start with a leading slash, e.g. ``/api/chat``.
        """
        url = f"{self.valves.OLLAMA_BASE_URL.rstrip('/')}{path}"
        return self._http_json(
            "POST",
            url,
            json_payload=payload,
        )

    def _plexintel_url(self, path: str) -> str:
        return f"{self.valves.PLEXINTEL_BASE_URL.rstrip('/')}{path}"

    def _http_json(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_payload: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        try:
            response = requests.request(
                method,
                url,
                params=params,
                json=json_payload,
                headers=headers,
                timeout=self.valves.REQUEST_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            raise PipelineHttpError(endpoint=url, detail=str(exc)) from exc

        if response.status_code >= 400:
            detail = response.text[:500] if response.text else response.reason
            raise PipelineHttpError(
                endpoint=url,
                status_code=response.status_code,
                detail=detail,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise PipelineHttpError(endpoint=url, status_code=response.status_code, detail="Invalid JSON") from exc

    def _handle_list_users(self) -> str:
        users = self._fetch_users()
        if not users:
            return "## PlexIntel Users\n\nNo PlexIntel users were returned."
        lines = ["## PlexIntel Users", ""]
        for user in users:
            lines.append(f"- `{user.get('username')}`{self._friendly_suffix(user)}")
        return "\n".join(lines)

    def _handle_recommendations(self, prompt: str, body: dict[str, Any]) -> str:
        users = self._fetch_users()
        resolution = self._resolve_user(prompt, body.get("user") or {}, users, require_user=True)
        if not resolution.ok:
            return self._render_user_clarification(resolution, users)

        limit = self._parse_limit(prompt)
        view = self._parse_view(prompt)
        params: dict[str, Any] = {
            "user": resolution.username,
            "limit": limit,
        }
        if view:
            params["view"] = view

        recommendations = self._plex_get("/api/agent/recommendations", params=params)
        items = list(recommendations.get("items") or [])[:limit]
        gallery = self._poster_gallery_for_items(items)
        narration = self._call_gemma_narration(
            prompt=prompt,
            username=resolution.username or "",
            view=view,
            items=items,
        )
        return self._render_recommendations(
            username=resolution.username or "",
            friendly_name=resolution.friendly_name,
            view=view,
            items=items,
            gallery=gallery,
            narration=narration,
        )

    def _handle_search(self, prompt: str) -> str:
        query = self._extract_search_query(prompt)
        if not query:
            return "## PlexIntel Library Search\n\nTell me what title, person, genre, or keyword to search for."
        limit = self._parse_limit(prompt, default=10)
        view = self._parse_view(prompt)
        params: dict[str, Any] = {"q": query, "limit": limit}
        media_type = self._view_to_media_type(view)
        if media_type:
            params["media_type"] = media_type
        results = self._plex_get("/api/agent/search", params=params)
        items = list(results.get("items") or [])[:limit]
        gallery = self._poster_gallery_for_items(items) if "poster" in prompt.lower() and items else None
        return self._render_search(query=query, items=items, gallery=gallery)

    def _handle_item_poster(self, prompt: str) -> str:
        rating_key = self._extract_rating_key(prompt)
        if rating_key is None:
            query = self._extract_search_query(prompt)
            if not query:
                return "## PlexIntel Poster\n\nTell me the `rating_key` or title to show."
            search = self._plex_get("/api/agent/search", params={"q": query, "limit": 1})
            items = list(search.get("items") or [])
            if not items:
                return f"## PlexIntel Poster\n\nNo library item matched `{query}`."
            item = items[0]
        else:
            item = self._plex_get(f"/api/agent/items/{rating_key}")

        gallery = self._poster_gallery_for_items([item])
        lines = [
            "## PlexIntel Poster",
            "",
            gallery.get("markdown") if gallery else "_Poster unavailable._",
            "",
            self._format_item_detail(item),
        ]
        return "\n".join(line for line in lines if line is not None)

    def _handle_watch_history(self, prompt: str, body: dict[str, Any]) -> str:
        users = self._fetch_users()
        first_person = self._mentions_first_person(prompt)
        named_resolution = self._resolve_user(
            prompt,
            body.get("user") or {},
            users,
            require_user=first_person,
        )
        if not named_resolution.ok and named_resolution.reason:
            return self._render_user_clarification(named_resolution, users)

        limit = self._parse_limit(prompt, default=10)
        params: dict[str, Any] = {"limit": limit}
        if named_resolution.username:
            params["user"] = named_resolution.username
        if re.search(r"\b(engaged|completed|finished)\b", prompt, flags=re.I):
            params["engaged_only"] = True

        history = self._plex_get("/api/agent/watch-history", params=params)
        return self._render_watch_history(
            username=named_resolution.username,
            items=list(history.get("results") or [])[:limit],
            engaged_only=bool(params.get("engaged_only")),
        )

    def _fetch_users(self) -> list[dict[str, Any]]:
        payload = self._plex_get("/api/agent/users", params={"limit": 1000})
        return list(payload.get("items") or [])

    def _resolve_user(
        self,
        prompt: str,
        openwebui_user: dict[str, Any],
        users: list[dict[str, Any]],
        *,
        require_user: bool,
    ) -> UserResolution:
        first_person = self._mentions_first_person(prompt)
        if first_person:
            alias_user = self._resolve_alias_user(openwebui_user, users)
            if alias_user:
                return self._resolution_from_user(alias_user)

            direct_matches = self._openwebui_identity_matches(openwebui_user, users)
            if len(direct_matches) == 1:
                return self._resolution_from_user(direct_matches[0])
            if len(direct_matches) > 1:
                return UserResolution(
                    username=None,
                    candidates=direct_matches,
                    reason="Your OpenWebUI identity matches multiple Plex users.",
                )
            return UserResolution(
                username=None,
                candidates=users,
                reason="I could not map your OpenWebUI user to a Plex user.",
            )

        named_matches = self._prompt_user_matches(prompt, users)
        if len(named_matches) == 1:
            return self._resolution_from_user(named_matches[0])
        if len(named_matches) > 1:
            return UserResolution(
                username=None,
                candidates=named_matches,
                reason="That user reference matches multiple Plex users.",
            )
        if require_user:
            return UserResolution(
                username=None,
                candidates=users,
                reason="I need a Plex user for this workflow.",
            )
        return UserResolution(username=None)

    def _mentions_first_person(self, prompt: str) -> bool:
        return bool(re.search(r"\b(me|my|mine|myself)\b", prompt, flags=re.I))

    def _load_aliases(self) -> dict[str, str]:
        try:
            raw = json.loads(self.valves.USER_ALIASES_JSON or "{}")
        except json.JSONDecodeError:
            return {}
        if not isinstance(raw, dict):
            return {}
        return {str(key).strip().casefold(): str(value).strip() for key, value in raw.items()}

    def _resolve_alias_user(
        self,
        openwebui_user: dict[str, Any],
        users: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        aliases = self._load_aliases()
        for value in self._openwebui_identity_values(openwebui_user):
            mapped = aliases.get(value.casefold())
            if mapped:
                matches = self._exact_user_matches(mapped, users)
                if len(matches) == 1:
                    return matches[0]
        return None

    def _openwebui_identity_matches(
        self,
        openwebui_user: dict[str, Any],
        users: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for value in self._openwebui_identity_values(openwebui_user):
            for user in self._exact_user_matches(value, users):
                if user not in matches:
                    matches.append(user)
        return matches

    def _openwebui_identity_values(self, openwebui_user: dict[str, Any]) -> list[str]:
        values = []
        for key in ("email", "name", "id", "username"):
            value = openwebui_user.get(key)
            if value is not None and str(value).strip():
                values.append(str(value).strip())
        return values

    def _prompt_user_matches(self, prompt: str, users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        matches = []
        for user in users:
            username = str(user.get("username") or "")
            friendly_name = str(user.get("friendly_name") or "")
            if self._contains_term(prompt, username) or self._contains_term(prompt, friendly_name):
                matches.append(user)
        return matches

    def _exact_user_matches(self, value: str, users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = value.strip().casefold()
        if not normalized:
            return []
        return [
            user
            for user in users
            if normalized in {
                str(user.get("username") or "").strip().casefold(),
                str(user.get("friendly_name") or "").strip().casefold(),
            }
        ]

    def _contains_term(self, prompt: str, term: str) -> bool:
        normalized = term.strip()
        if not normalized:
            return False
        if " " in normalized:
            return normalized.casefold() in prompt.casefold()
        return bool(re.search(rf"\b{re.escape(normalized)}\b", prompt, flags=re.I))

    def _resolution_from_user(self, user: dict[str, Any]) -> UserResolution:
        return UserResolution(
            username=user.get("username"),
            friendly_name=user.get("friendly_name"),
        )

    def _parse_view(self, prompt: str) -> str | None:
        text = prompt.lower()
        if re.search(r"\bepisodes?\b", text):
            return "episodes"
        if re.search(r"\bseasons?\b", text):
            return "seasons"
        if re.search(r"\b(tv|shows|series)\b", text):
            return "shows"
        if re.search(r"\bmovies?\b", text):
            return "movies"
        if re.search(r"\ball\b", text):
            return "all"
        return None

    def _view_to_media_type(self, view: str | None) -> str | None:
        return {
            "movies": "movie",
            "episodes": "episode",
            "shows": "show",
        }.get(view or "")

    def _parse_limit(self, prompt: str, default: Optional[int] = None) -> int:
        fallback = default if default is not None else self.valves.DEFAULT_LIMIT
        patterns = [
            r"\btop\s+(\d{1,2})\b",
            r"\bshow(?: me)?\s+(\d{1,2})\b",
            r"\bgive(?: me)?\s+(\d{1,2})\b",
            r"\blimit(?: to)?\s+(\d{1,2})\b",
            r"\b(\d{1,2})\s+(?:recommendations|recs|picks|items|movies|shows|episodes)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.I)
            if match:
                return max(1, min(int(match.group(1)), self.valves.MAX_LIMIT))
        return max(1, min(int(fallback), self.valves.MAX_LIMIT))

    def _extract_rating_key(self, prompt: str) -> int | None:
        match = re.search(r"\brating[_ -]?key\s*[:#]?\s*(\d+)\b", prompt, flags=re.I)
        if not match:
            return None
        return int(match.group(1))

    def _extract_search_query(self, prompt: str) -> str:
        patterns = [
            r"\bsearch(?:\s+the)?\s+library(?:\s+for)?\s+(.+)$",
            r"\bsearch\s+for\s+(.+)$",
            r"\blook\s+up\s+(.+)$",
            r"\bfind\s+(.+)$",
            r"\bposter\s+(?:for|of)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.I)
            if match:
                return self._clean_query(match.group(1))
        return self._clean_query(prompt)

    def _clean_query(self, value: str) -> str:
        cleaned = re.sub(r"\brating[_ -]?key\s*[:#]?\s*\d+\b", "", value, flags=re.I)
        cleaned = re.sub(r"\bwith\s+posters?\b", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(in|from)\s+(my\s+)?library\b", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\btop\s+\d{1,2}\b", "", cleaned, flags=re.I)
        cleaned = cleaned.strip(" \"'?.!")
        return re.sub(r"\s+", " ", cleaned).strip()

    def _poster_gallery_for_items(self, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not items:
            return None
        payload_items = [
            {
                "rating_key": item.get("rating_key"),
                "title": item.get("title"),
                "media_type": item.get("media_type"),
            }
            for item in items
            if item.get("rating_key") is not None
        ]
        if not payload_items:
            return None
        return self._plex_post(
            "/api/agent/poster-gallery",
            {"items": payload_items, "width": self.valves.POSTER_WIDTH},
        )

    def _call_gemma_narration(
        self,
        *,
        prompt: str,
        username: str,
        view: str | None,
        items: list[dict[str, Any]],
    ) -> str | None:
        if not self.valves.ENABLE_GEMMA_NARRATION:
            return None
        # Determine which backend to use for narration.
        # Prefer Ollama if its configuration is present; otherwise fall back to OpenWebUI.
        use_ollama = bool(self.valves.OLLAMA_BASE_URL and self.valves.OLLAMA_MODEL)
        if not use_ollama and (not self.valves.OPENWEBUI_API_KEY or not self.valves.OPENWEBUI_BASE_URL):
            return None
        facts = [
            {
                "rank": index,
                "title": item.get("title"),
                "media_type": item.get("media_type"),
                "score": item.get("score"),
                "year": item.get("year"),
                "genres": item.get("genres"),
                "explanation": item.get("explanation"),
            }
            for index, item in enumerate(items, start=1)
        ]
        payload = {
            "model": self.valves.OLLAMA_MODEL if use_ollama else self.valves.GEMMA_MODEL,
            "stream": False,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Write one concise paragraph explaining these PlexIntel recommendations. "
                        "Use only the supplied facts. Do not add titles, ranks, posters, tables, "
                        "or change the order."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_request": prompt,
                            "plex_user": username,
                            "view": view or "all",
                            "items": facts,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        try:
            if use_ollama:
                response = self._ollama_post("/api/chat", payload)
            else:
                response = self._openwebui_post("/api/chat/completions", payload)
        except PipelineHttpError:
            return None
        content = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        if not isinstance(content, str):
            return None
        return self._clean_narration(content)

    def _clean_narration(self, content: str) -> str | None:
        cleaned = " ".join(line.strip().lstrip("#-* ") for line in content.splitlines() if line.strip())
        if not cleaned:
            return None
        if len(cleaned) > 700:
            cleaned = cleaned[:697].rstrip() + "..."
        return cleaned

    def _render_recommendations(
        self,
        *,
        username: str,
        friendly_name: str | None,
        view: str | None,
        items: list[dict[str, Any]],
        gallery: dict[str, Any] | None,
        narration: str | None,
    ) -> str:
        label = f"{username}{f' ({friendly_name})' if friendly_name else ''}"
        lines = [
            "# PlexIntel Ultimate Recommendations",
            "",
            f"**User:** `{label}`  ",
            f"**View:** `{view or 'all'}`  ",
            f"**Showing:** `{len(items)}`",
            "",
            "## Poster Gallery",
            "",
        ]
        if gallery and gallery.get("markdown"):
            lines.append(gallery["markdown"])
        else:
            lines.append("_Poster gallery unavailable._")
        lines.extend(["", "## Ranked Picks", ""])

        if not items:
            lines.append("No recommendations matched this request.")
        for index, item in enumerate(items, start=1):
            lines.extend(self._format_ranked_item(index, item))

        if narration:
            lines.extend(["", "## Gemma Notes", "", narration])
        return "\n".join(lines).strip()

    def _format_ranked_item(self, index: int, item: dict[str, Any]) -> list[str]:
        score = item.get("score")
        score_text = f"{float(score) * 100:.0f}%" if isinstance(score, (int, float)) else "n/a"
        title = item.get("title") or f"rating_key {item.get('rating_key')}"
        year = f" ({item.get('year')})" if item.get("year") else ""
        media = item.get("media_type") or "unknown"
        lines = [
            f"{index}. **{title}**{year} - `{media}` - score `{score_text}`",
        ]
        context = self._series_context(item)
        if context:
            lines.append(f"   - Context: {context}")
        for label, key in (("Genres", "genres"), ("Cast", "actors"), ("Directors", "directors")):
            if item.get(key):
                lines.append(f"   - {label}: {item[key]}")
        reason = item.get("explanation") or item.get("summary")
        if reason:
            lines.append(f"   - Why: {self._truncate(str(reason), 220)}")
        return lines

    def _series_context(self, item: dict[str, Any]) -> str | None:
        pieces = []
        if item.get("show_title"):
            pieces.append(str(item["show_title"]))
        if item.get("season_number") is not None:
            pieces.append(f"S{int(item['season_number']):02d}")
        if item.get("episode_number") is not None:
            pieces.append(f"E{int(item['episode_number']):02d}")
        return " ".join(pieces) if pieces else None

    def _render_search(
        self,
        *,
        query: str,
        items: list[dict[str, Any]],
        gallery: dict[str, Any] | None,
    ) -> str:
        lines = ["## PlexIntel Library Search", "", f"**Query:** `{query}`", ""]
        if gallery and gallery.get("markdown"):
            lines.extend(["### Posters", "", gallery["markdown"], ""])
        lines.append("### Results")
        lines.append("")
        if not items:
            lines.append("No library items matched this query.")
        for index, item in enumerate(items, start=1):
            lines.append(f"{index}. {self._format_item_detail(item)}")
        return "\n".join(lines).strip()

    def _render_watch_history(
        self,
        *,
        username: str | None,
        items: list[dict[str, Any]],
        engaged_only: bool,
    ) -> str:
        scope = f"`{username}`" if username else "all users"
        lines = [
            "## PlexIntel Watch History",
            "",
            f"**Scope:** {scope}  ",
            f"**Engaged only:** `{str(engaged_only).lower()}`",
            "",
        ]
        if not items:
            lines.append("No watch-history rows matched this request.")
        for index, item in enumerate(items, start=1):
            watched = item.get("watched_at") or "unknown time"
            title = item.get("title") or f"rating_key {item.get('rating_key')}"
            user = item.get("username") or "unknown user"
            pct = item.get("percent_complete")
            pct_text = f"{float(pct) * 100:.0f}%" if isinstance(pct, (int, float)) else "n/a"
            lines.append(f"{index}. **{title}** - `{user}` - `{watched}` - `{pct_text}` complete")
        return "\n".join(lines)

    def _format_item_detail(self, item: dict[str, Any]) -> str:
        title = item.get("title") or f"rating_key {item.get('rating_key')}"
        year = f" ({item.get('year')})" if item.get("year") else ""
        media = item.get("media_type") or "unknown"
        rating_key = item.get("rating_key")
        return f"**{title}**{year} - `{media}` - rating_key `{rating_key}`"

    def _render_user_clarification(
        self,
        resolution: UserResolution,
        fallback_users: list[dict[str, Any]],
    ) -> str:
        candidates = resolution.candidates or fallback_users
        lines = [
            "## Which Plex user?",
            "",
            resolution.reason or "I need a Plex username before running this workflow.",
            "",
            "Ask again with one of these Plex users:",
            "",
        ]
        for user in candidates[:20]:
            lines.append(f"- `{user.get('username')}`{self._friendly_suffix(user)}")
        return "\n".join(lines)

    def _render_http_error(self, exc: PipelineHttpError) -> str:
        lines = [
            "## PlexIntel Request Failed",
            "",
            f"**Endpoint:** `{exc.endpoint}`",
        ]
        if exc.status_code is not None:
            lines.append(f"**Status:** `{exc.status_code}`")
        if exc.detail:
            lines.extend(["", "```text", exc.detail, "```"])
        return "\n".join(lines)

    def _friendly_suffix(self, user: dict[str, Any]) -> str:
        friendly = user.get("friendly_name")
        return f" ({friendly})" if friendly else ""

    def _truncate(self, value: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", value).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."
