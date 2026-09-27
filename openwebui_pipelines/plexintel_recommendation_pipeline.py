"""
title: PlexIntel Recommendation Pipeline
author: jmnovak
version: 0.1.8
requirements: requests
description: Deterministic PlexIntel workflows with optional Ollama Gemma narration.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
        POSTER_BASE_URL: str = Field(
            default="",
            description=(
                "Optional browser-visible base URL for poster images. Leave blank to use "
                "PLEXINTEL_BASE_URL."
            ),
        )
        POSTER_PATH_PREFIX: str = Field(
            default="/api/posters",
            description=(
                "Browser-visible path prefix for poster images. Use this when PlexIntel is "
                "published behind a reverse-proxy prefix, e.g. /plexintel/api/posters."
            ),
        )
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
        WATCH_HISTORY_TIMEZONE: str = Field(default="America/Chicago", description="Timezone for watch-history dates and naive timestamps.")
        DEFAULT_LIMIT: int = Field(default=8, ge=1)
        MAX_LIMIT: int = Field(default=20, ge=1)
        POSTER_WIDTH: int = Field(default=180, ge=1, le=1200)
        REQUEST_TIMEOUT_S: int = Field(default=30, ge=1)

    def __init__(self):
        self.id = "plexintel_recommendations"
        self.name = "PlexIntel Recommendations"
        self.description = "Deterministic PlexIntel recommendation, search, poster, and watch-history workflows."
        self.version = "0.1.8"
        self.valves = self.Valves(
            PLEXINTEL_BASE_URL=os.getenv("PLEXINTEL_BASE_URL", "http://192.168.1.9:8489"),
            POSTER_BASE_URL=os.getenv("POSTER_BASE_URL", ""),
            POSTER_PATH_PREFIX=os.getenv("POSTER_PATH_PREFIX", "/api/posters"),
            OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud"),
            ENABLE_GEMMA_NARRATION=_env_bool("ENABLE_GEMMA_NARRATION", True),
            USER_ALIASES_JSON=os.getenv("USER_ALIASES_JSON", "{}"),
            WATCH_HISTORY_TIMEZONE=os.getenv("WATCH_HISTORY_TIMEZONE", "America/Chicago"),
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
            if workflow == "highest_rated":
                params = {"q": "", "sort_by": "rating", "sort_dir": "desc", "limit": self._parse_limit(prompt)}
                media_type = self._view_to_media_type(self._parse_view(prompt))
                if media_type:
                    params["media_type"] = media_type
                result = self._plex_get("/api/agent/search", params=params)
                lines = ["## Highest Rated", "", "Ranked by metadata rating.", ""]
                for item in result.get("items") or []:
                    lines.append(f"- {self._format_item_detail(item)} — rating {item.get('rating') if item.get('rating') is not None else 'unavailable'}")
                return "\n".join(lines)
            if workflow == "popular_measure":
                return "Popularity can mean most plays or most unique viewers. Ask for either measure; highest rated uses metadata ratings."
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
        if self._history_is_server_wide(prompt) or re.search(r"\b(watch history|watched|viewing history|recent viewing)\b", text):
            # A plain user-list request is not a request for viewing activity.
            if not re.fullmatch(r"(?:list|show)(?: me)? (?:all )?(?:plex )?users[?.!]?", text.strip()):
                return "watch_history"
        if re.search(r"\b(list|show|who are|what are)\b.*\b(users|plex users)\b", text):
            return "list_users"
        if re.search(r"\bhighest[- ]rated\b", text):
            return "highest_rated"
        if re.search(r"\bpopular\b", text):
            return "popular_measure"
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
        # Resolve scope before issuing any history request.
        users = self._fetch_users()
        server_wide = self._history_is_server_wide(prompt)
        username = None
        if not server_wide:
            identity_prompt = re.sub(r"\b(show|tell|give)\s+me\b", r"\1", prompt, flags=re.I)
            resolution = self._resolve_user(
                identity_prompt, body.get("user") or {}, users, require_user=True,
            )
            if not resolution.ok:
                return self._render_user_clarification(resolution, users)
            username = resolution.username

        viewer_query = bool(re.search(r"\b(who\s+(?:has\s+)?watched|(?:has|did)\s+anyone\s+(?:watched|watch))\b", prompt, re.I))
        rating_key = self._extract_rating_key(prompt)
        title = self._history_title(prompt) if viewer_query and rating_key is None else None
        if viewer_query and rating_key is None and (not title or title.casefold() in {"this", "it", "that"}):
            return "Which title or rating_key should I check across all users?"

        # A title such as "Yesterday" or "Engaged" is not a history filter.
        filter_prompt = re.sub(re.escape(title), "", prompt, count=1, flags=re.I) if title else prompt
        try:
            start, end, window_label = self._history_window(filter_prompt)
        except ValueError as exc:
            return str(exc)
        partial_requested = bool(re.search(
            r"\b(?:even|including|include|and|or)\s+partial(?:ly)?\b|"
            r"\bnot\s+(?:completed|finished|engaged)\b", filter_prompt, re.I,
        ))
        completed_only = not partial_requested and bool(re.search(r"\b(completed|finished)\b", filter_prompt, re.I))
        engaged_only = not partial_requested and (completed_only or bool(re.search(r"\bengaged\b", filter_prompt, re.I)))
        targets = [u["username"] for u in users] if server_wide else [username]
        merged = []
        failures = []
        for target in targets:
            try:
                rows = self._fetch_history_for_user(target, engaged_only)
                merged.extend(rows)
            except (PipelineHttpError, ValueError) as exc:
                failures.append(f"`{target}`: {exc}")

        # Filter only after every user's pages have been fetched and merged.
        items = []
        undated = 0
        for row in merged:
            if start is not None or end is not None:
                watched = self._history_timestamp(row.get("watched_at"))
                if watched is None:
                    undated += 1
                    continue
                if (start is not None and watched < start) or (end is not None and watched >= end):
                    continue
            if rating_key is not None and str(row.get("rating_key")) != str(rating_key):
                continue
            if title and not any(str(row.get(key) or "").casefold() == title.casefold() for key in ("title", "show_title")):
                continue
            if completed_only and float(row.get("percent_complete") or 0) < 1:
                continue
            items.append(row)

        limit = self._parse_limit(prompt, default=10)
        scope = f"`{username}`" if username else f"all users ({len(targets) - len(failures)}/{len(targets)} queried successfully)"
        lines = [
            "## PlexIntel Watch History", "", f"**Scope:** {scope}",
            f"**Window:** {window_label}",
            f"**Viewing:** {'completed (100%)' if completed_only else 'engaged (>=50%)' if engaged_only else 'all playback, including partial plays'}", "",
        ]
        if failures:
            lines += ["**Incomplete coverage:** " + "; ".join(failures),
                      "Results below cover successful queries only; no server-wide absence or definitive ranking can be established.", ""]
        if undated:
            lines += [f"Incomplete time coverage: excluded {undated} playback events with unknown times from the requested window.", ""]
        if not items:
            lines.append("No matching playback events in the retrieved data." if failures or undated else "No playback events matched this request.")
            return "\n".join(lines)

        popularity = bool(re.search(r"\b(most watched|most viewers|most plays|most popular|popular by viewing)\b", prompt, re.I))
        active = bool(re.search(r"\bwho\s+(?:has\s+been|is|was)\s+active\b", prompt, re.I))
        if popularity and not viewer_query:
            view = self._parse_view(prompt)
            if re.search(r"\b(?:most watched|most popular)\s+(?:tv\s+)?show\b|\bshow\s+(?:with|has)\s+(?:the\s+)?most", prompt, re.I):
                view = "shows"
            if view == "movies":
                items = [row for row in items if row.get("media_type") == "movie"]
            elif view in {"shows", "episodes"}:
                items = [row for row in items if row.get("media_type") in {"episode", "show"}]
            groups = {}
            for row in items:
                label = (row.get("show_title") or row.get("title")) if view == "shows" else row.get("title")
                key = label if view == "shows" else row.get("rating_key")
                group = groups.setdefault(key, {"label": label or str(key), "plays": 0, "viewers": set()})
                group["plays"] += 1
                group["viewers"].add(row["username"])
            by_viewers = bool(re.search(r"\bmost viewers\b", prompt, re.I))
            ranked = sorted(groups.values(), key=lambda g: (-(len(g["viewers"]) if by_viewers else g["plays"]), -g["plays"], g["label"]))
            lines.append("Ranked by " + ("unique viewers." if by_viewers else "playback events."))
            for index, group in enumerate(ranked[:limit], 1):
                lines.append(f'{index}. **{group["label"]}** — {group["plays"]} playback events; {len(group["viewers"])} unique viewers')
            if not ranked:
                lines.append("No matching playback events for this media type.")
        elif viewer_query or active:
            groups = {}
            for row in items:
                groups.setdefault(row["username"], []).append(row)
            if viewer_query:
                lines.append(f"**Title:** {title or f'rating_key {rating_key}'}")
            lines.append(f"{len(items)} playback events; {len(groups)} unique viewers.")
            for user, rows in sorted(groups.items()):
                completed = sum(float(row.get("percent_complete") or 0) >= 1 for row in rows)
                engaged = sum(row.get("engaged") is True or float(row.get("percent_complete") or 0) >= .5 for row in rows)
                partial = sum(row.get("percent_complete") is not None and float(row["percent_complete"]) < 1 for row in rows)
                lines.append(f"- `{user}`: {len(rows)} playback events; {engaged} engaged; {completed} completed; {partial} partial.")
            lines.append("Engaged (>=50%) can overlap partial (<100%) playback.")
        else:
            items.sort(key=lambda row: self._history_timestamp(row.get("watched_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            lines.append(f"{len(items)} playback events; {len({row['username'] for row in items})} unique viewers. Showing {min(limit, len(items))}.")
            for index, row in enumerate(items[:limit], 1):
                pct = row.get("percent_complete")
                progress = f"{float(pct) * 100:.0f}% complete" if pct is not None else "unknown completion"
                title_label = row.get("title") or f"rating_key {row.get('rating_key')}"
                if row.get("show_title"):
                    title_label = f"{row['show_title']} — {title_label}"
                status = "completed" if pct is not None and float(pct) >= 1 else "partial" if pct is not None else "unknown"
                lines.append(f"{index}. **{title_label}** — `{row['username']}` — {row.get('watched_at') or 'unknown time'} — {progress} ({status})")
        return "\n".join(lines)

    def _history_is_server_wide(self, prompt: str) -> bool:
        return bool(re.search(
            r"\b(all\s+(?:watch\s+history|users)|everyone(?:'s)?|everybody|server[- ]wide|"
            r"who\s+(?:has\s+)?watched|(?:has|did)\s+anyone\s+(?:watched|watch)|"
            r"what\s+(?:was|has\s+been)\s+watched|most\s+(?:watched|viewers|plays|popular)|"
            r"popular\s+by\s+viewing|people\s+(?:are\s+)?watching|"
            r"who\s+(?:has\s+been|is|was)\s+active)\b", prompt, re.I,
        ))

    def _fetch_history_for_user(self, username: str, engaged_only: bool) -> list[dict[str, Any]]:
        items = []
        seen_ids = set()
        offset = 0
        while True:
            page = self._plex_get("/api/agent/watch-history", params={
                "user": username, "limit": 200, "engaged_only": engaged_only, "offset": offset,
            })
            rows = list(page.get("results") or [])
            if page.get("user") != username or any(row.get("username") != username for row in rows):
                raise ValueError("history response did not match the requested username")
            for row in rows:
                watch_id = row.get("watch_id")
                if watch_id is None:
                    raise ValueError("history response is missing playback event IDs")
                if watch_id not in seen_ids:
                    seen_ids.add(watch_id)
                    items.append(row)
            next_offset = page.get("next_offset")
            if next_offset is None:
                if "next_offset" not in page and len(rows) >= 200:
                    raise ValueError("history may be truncated; update the PlexIntel API for pagination")
                return items
            if not isinstance(next_offset, int) or next_offset <= offset:
                raise ValueError("invalid history pagination")
            offset = next_offset

    def _fetch_users(self) -> list[dict[str, Any]]:
        users = {}
        offset = 0
        while True:
            payload = self._plex_get("/api/agent/users", params={"limit": 1000, "offset": offset})
            rows = list(payload.get("items") or [])
            for user in rows:
                if not user.get("username"):
                    raise ValueError("user listing is missing a username")
                users[user["username"]] = user
            next_offset = payload.get("next_offset")
            if next_offset is None:
                if "next_offset" not in payload and len(rows) >= 1000:
                    raise ValueError("user listing may be truncated; update the PlexIntel API for pagination")
                return list(users.values())
            if not isinstance(next_offset, int) or next_offset <= offset:
                raise ValueError("invalid user pagination")
            offset = next_offset

    def _history_now(self) -> datetime:
        return datetime.now(ZoneInfo(self.valves.WATCH_HISTORY_TIMEZONE))

    def _history_timestamp(self, value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo(self.valves.WATCH_HISTORY_TIMEZONE))
        except (TypeError, ValueError):
            return None

    def _history_window(self, prompt: str) -> tuple[datetime | None, datetime | None, str]:
        now = self._history_now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        text = prompt.casefold()
        start = end = None
        match = re.search(r"\b(?:last|past)\s+(\d+)\s+(hours?|days?|weeks?)\b", text)
        dates = re.findall(
            r"\b\d{4}-\d{2}-\d{2}(?:(?:t| )\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:z|[+-]\d{2}:\d{2})?)?\b",
            text,
        )
        if dates:
            parsed = [datetime.fromisoformat(value.replace("z", "+00:00")) for value in dates]
            parsed = [value if value.tzinfo else value.replace(tzinfo=now.tzinfo) for value in parsed]
            if len(parsed) == 2 and re.search(r"\b(between|from)\b", text):
                start = parsed[0]
                end = parsed[1] + (timedelta(days=1) if len(dates[1]) == 10 else timedelta())
            elif len(parsed) == 1:
                date_pattern = re.escape(dates[0])
                if re.search(r"\b(?:since|after)\s+" + date_pattern, text):
                    after_step = timedelta(days=1) if len(dates[0]) == 10 else timedelta(microseconds=1)
                    start = parsed[0] + (after_step if re.search(r"\bafter\s+" + date_pattern, text) else timedelta())
                elif re.search(r"\b(?:before|until)\s+" + date_pattern, text):
                    end = parsed[0]
                elif re.search(r"\bon\s+" + date_pattern, text) and len(dates[0]) == 10:
                    start, end = parsed[0], parsed[0] + timedelta(days=1)
                else:
                    raise ValueError("Use on, since, before, or between with YYYY-MM-DD dates.")
            else:
                raise ValueError("Use a single date or a between/from date range.")
        elif match:
            amount = int(match.group(1))
            if amount < 1:
                raise ValueError("The history window must be positive.")
            unit = match.group(2).rstrip("s") + "s"
            start, end = now - timedelta(**{unit: amount}), now
        elif "yesterday" in text:
            start, end = today - timedelta(days=1), today
        elif "today" in text:
            start, end = today, now
        elif "this week" in text:
            start, end = today - timedelta(days=today.weekday()), now
        elif "last week" in text:
            end = today - timedelta(days=today.weekday())
            start = end - timedelta(days=7)
        elif "this month" in text:
            start, end = today.replace(day=1), now
        elif "last month" in text:
            end = today.replace(day=1)
            start = (end - timedelta(days=1)).replace(day=1)
        elif re.search(r"\b(?:last|past|this)\s+(?:\d+|year|weekend|quarter)|\b(?:since|before|after|during|on)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|May|June|July|August|September|October|November|December)\b", text, re.I):
            raise ValueError("Use today, yesterday, this/last week or month, last N days/hours/weeks, or YYYY-MM-DD dates for a history window.")
        if start is not None and end is not None and start >= end:
            raise ValueError("The history window must end after it starts.")
        label = "all available history" if start is None and end is None else f"{start.isoformat() if start else 'earliest'} to {end.isoformat() if end else 'latest'} (end exclusive)"
        return start, end, label

    def _history_title(self, prompt: str) -> str | None:
        match = re.search(r"\b(?:who\s+(?:has\s+)?watched|(?:has|did)\s+anyone\s+(?:watched|watch))\s+(.+)", prompt, re.I)
        if not match:
            return None
        title = match.group(1).strip().rstrip("?.!")
        quoted = re.match(r'["“](.+?)["”]', title)
        if quoted:
            return quoted.group(1)
        title = re.split(r"\s+(?:(?:over|in)\s+the\s+)?(?:last\s+\d+\s+(?:days?|hours?|weeks?)|past\s+\d+\s+(?:days?|hours?|weeks?)|this\s+(?:week|month)|last\s+(?:week|month)|today|yesterday|since\s+\d{4}-|before\s+\d{4}-|after\s+\d{4}-|on\s+\d{4}-|between\s+\d{4}-|from\s+\d{4}-|even\s+partially|including\s+partial|(?:completed|finished|engaged)\s+only)", title, maxsplit=1, flags=re.I)[0]
        return title.strip().strip('"').rstrip(",?.!")

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
        return bool(re.search(r"\b(i|me|my|mine|myself)\b", prompt, flags=re.I))

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
        try:
            gallery = self._plex_post(
                "/api/agent/poster-gallery",
                {"items": payload_items, "width": self.valves.POSTER_WIDTH},
            )
            return self._normalize_gallery_urls(gallery)
        except PipelineHttpError as exc:
            if exc.status_code not in {404, 405}:
                raise
            return self._build_local_poster_gallery(payload_items)

    def _build_local_poster_gallery(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        poster_items = []
        markdown_blocks = []
        width = self.valves.POSTER_WIDTH

        for item in items:
            rating_key = item.get("rating_key")
            if rating_key is None:
                continue
            title = str(item.get("title") or f"rating_key {rating_key}")
            media_type = item.get("media_type")
            poster_url = self._poster_url(rating_key)
            alt = f"Poster for {title}".replace("\\", "\\\\").replace("]", "\\]")
            markdown = f"![{alt}]({poster_url})"
            poster_items.append(
                {
                    "rating_key": rating_key,
                    "title": title,
                    "media_type": media_type,
                    "poster_url": poster_url,
                    "image_url": poster_url,
                    "url": poster_url,
                    "markdown": markdown,
                    "html": f'<img src="{poster_url}" alt="Poster for {title}" width="{width}" />',
                }
            )
            markdown_blocks.append(f"### {title}\n{markdown}")

        return {
            "count": len(poster_items),
            "items": poster_items,
            "markdown": "\n\n".join(markdown_blocks),
        }

    def _normalize_gallery_urls(self, gallery: dict[str, Any]) -> dict[str, Any]:
        items = gallery.get("items")
        if not isinstance(items, list):
            return gallery

        normalized_items = []
        markdown_blocks = []
        for item in items:
            if not isinstance(item, dict):
                continue
            rating_key = item.get("rating_key")
            if rating_key is None:
                normalized_items.append(item)
                continue
            title = str(item.get("title") or f"rating_key {rating_key}")
            poster_url = self._poster_url(rating_key)
            markdown = f"![{self._markdown_alt(title)}]({poster_url})"
            normalized_item = dict(item)
            normalized_item.update(
                {
                    "poster_url": poster_url,
                    "image_url": poster_url,
                    "url": poster_url,
                    "markdown": markdown,
                    "html": self._poster_img_tag(poster_url, title),
                }
            )
            normalized_items.append(normalized_item)
            markdown_blocks.append(f"### {title}\n{markdown}")

        normalized_gallery = dict(gallery)
        normalized_gallery["items"] = normalized_items
        normalized_gallery["markdown"] = "\n\n".join(markdown_blocks)
        return normalized_gallery

    def _poster_url(self, rating_key: Any) -> str:
        base_url = (self.valves.POSTER_BASE_URL or self.valves.PLEXINTEL_BASE_URL).rstrip("/")
        path_prefix = "/" + (self.valves.POSTER_PATH_PREFIX or "/api/posters").strip("/")
        return f"{base_url}{path_prefix}/{rating_key}?w={self.valves.POSTER_WIDTH}"

    def _markdown_alt(self, title: str) -> str:
        return f"Poster for {title}".replace("\\", "\\\\").replace("]", "\\]")

    def _poster_img_tag(self, poster_url: str, title: str) -> str:
        return (
            f'<img src="{self._html_attr(poster_url)}" '
            f'alt="{self._html_attr(f"Poster for {title}")}" '
            f'width="{int(self.valves.POSTER_WIDTH)}" />'
        )

    def _html_attr(self, value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
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
        if not self.valves.OLLAMA_BASE_URL or not self.valves.OLLAMA_MODEL:
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
            "model": self.valves.OLLAMA_MODEL,
            "stream": False,
            "options": {"temperature": 0.2},
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
            response = self._ollama_post("/api/chat", payload)
        except PipelineHttpError:
            return None
        content = response.get("message", {}).get("content")
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
            "## Ranked Picks",
            "",
        ]

        if not items:
            lines.append("No recommendations matched this request.")
        poster_items = self._gallery_items_by_rating_key(gallery)
        for index, item in enumerate(items, start=1):
            poster_item = poster_items.get(item.get("rating_key"))
            lines.extend(self._format_ranked_item(index, item, poster_item))

        if narration:
            lines.extend(["", "## Gemma Notes", "", narration])
        return "\n".join(lines).strip()

    def _gallery_items_by_rating_key(self, gallery: dict[str, Any] | None) -> dict[Any, dict[str, Any]]:
        if not gallery:
            return {}
        gallery_items = gallery.get("items")
        if not isinstance(gallery_items, list):
            return {}
        return {
            gallery_item.get("rating_key"): gallery_item
            for gallery_item in gallery_items
            if isinstance(gallery_item, dict) and gallery_item.get("rating_key") is not None
        }

    def _format_ranked_item(
        self,
        index: int,
        item: dict[str, Any],
        poster_item: dict[str, Any] | None = None,
    ) -> list[str]:
        score = item.get("score")
        score_text = f"{float(score) * 100:.0f}%" if isinstance(score, (int, float)) else "n/a"
        title = item.get("title") or f"rating_key {item.get('rating_key')}"
        year = f" ({item.get('year')})" if item.get("year") else ""
        media = item.get("media_type") or "unknown"
        lines = [
            f"{index}. **{title}**{year} - `{media}` - score `{score_text}`",
        ]
        poster_markup = self._inline_poster_markup(poster_item, str(title))
        if poster_markup:
            lines.extend(["", f"   {poster_markup}"])
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

    def _inline_poster_markup(self, poster_item: dict[str, Any] | None, title: str) -> str | None:
        if not poster_item:
            return None
        markdown = poster_item.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            return markdown.strip()
        poster_url = poster_item.get("poster_url") or poster_item.get("image_url") or poster_item.get("url")
        if not poster_url:
            return None
        return f"![{self._markdown_alt(title)}]({poster_url})"

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
