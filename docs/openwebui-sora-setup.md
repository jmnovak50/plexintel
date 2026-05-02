# OpenWebUI Sora Tool Setup

PlexIntel should store generated Sora MP4 files locally on the Raspberry Pi. OpenWebUI on the NAS should only call PlexIntel and stream the returned `stream_url`.

## Prerequisites

On the Raspberry Pi running PlexIntel:

```env
OPENAI_API_KEY=...
SORA_STORAGE_ROOT=/home/jmnovak/.sora
SORA_DEFAULT_MODEL=sora-2
SORA_DEFAULT_SIZE=1280x720
SORA_DEFAULT_SECONDS=8
SORA_RETENTION_HOURS=24
```

Make sure the NAS running OpenWebUI can reach PlexIntel over HTTPS or HTTP, for example:

```text
https://plexintel.kabolly.com/api/agent/video
```

## OpenWebUI Tool

Create a Workspace Tool in OpenWebUI named `PlexIntel Sora Video Tools`, then paste this code.

```python
"""
title: PlexIntel Sora Video Tools
author: jmnovak
version: 0.1.0
description: Create Sora videos through PlexIntel and render completed videos in OpenWebUI.
"""

import time
import requests
from typing import Optional

from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        PLEXINTEL_BASE_URL: str = Field(
            default="https://plexintel.kabolly.com",
            description="Base URL for PlexIntel, without a trailing slash.",
        )
        DEFAULT_MODEL: str = Field(default="sora-2", description="sora-2 or sora-2-pro.")
        DEFAULT_SIZE: str = Field(default="1280x720", description="Sora video size.")
        DEFAULT_SECONDS: str = Field(default="8", description='Must be "4", "8", or "12".')
        POLL_SECONDS: int = Field(default=10, description="Seconds between status polls.")
        MAX_POLLS: int = Field(default=60, description="Maximum status polls before timeout.")

    def __init__(self):
        self.valves = self.Valves()

    def _base_url(self) -> str:
        return self.valves.PLEXINTEL_BASE_URL.rstrip("/")

    def _user_id(self, __user__: Optional[dict] = None) -> str:
        if not __user__:
            return "unknown_user"
        return (
            __user__.get("email")
            or __user__.get("name")
            or __user__.get("id")
            or "unknown_user"
        )

    def create_sora_video(
        self,
        prompt: str,
        model: str = "sora-2",
        size: str = "1280x720",
        seconds: str = "8",
        __user__: Optional[dict] = None,
    ) -> dict:
        """
        Create a Sora video job through PlexIntel. Returns the video job id and status.
        Use this first when the user asks to generate a video.

        :param prompt: The video prompt.
        :param model: sora-2 or sora-2-pro.
        :param size: 1280x720, 720x1280, 1024x1792, or 1792x1024.
        :param seconds: Must be "4", "8", or "12".
        """

        url = f"{self._base_url()}/api/agent/video"
        payload = {
            "prompt": prompt,
            "model": model or self.valves.DEFAULT_MODEL,
            "size": size or self.valves.DEFAULT_SIZE,
            "seconds": str(seconds or self.valves.DEFAULT_SECONDS),
            "openwebui_user_id": self._user_id(__user__),
        }

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    def get_sora_video_status(self, video_id: str) -> dict:
        """
        Check the status of a Sora video job.

        :param video_id: The Sora video id returned by create_sora_video.
        """

        url = f"{self._base_url()}/api/agent/video/{video_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def _download_sora_video_payload(
        self,
        video_id: str,
        __user__: Optional[dict] = None,
    ) -> dict:
        url = f"{self._base_url()}/api/agent/video/{video_id}/download"
        response = requests.post(
            url,
            json={"openwebui_user_id": self._user_id(__user__)},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()

    def download_sora_video(
        self,
        video_id: str,
        __user__: Optional[dict] = None,
    ) -> tuple[HTMLResponse, dict]:
        """
        Download a completed Sora video into PlexIntel local temporary storage and embed it in chat.

        :param video_id: The Sora video id.
        """

        stored = self._download_sora_video_payload(video_id, __user__=__user__)
        stream_url = stored.get("stream_url")
        if not stream_url:
            raise RuntimeError(f"Video completed but no stream_url returned: {stored}")

        embed = self.render_sora_video(
            stream_url=stream_url,
            title=f"Sora video: {video_id}",
        )
        return embed, stored

    def render_sora_video(
        self,
        stream_url: str,
        title: str = "Generated Sora Video",
    ) -> HTMLResponse:
        """
        Render a stored Sora video directly in OpenWebUI as an embedded video player.

        :param stream_url: The stream_url returned by download_sora_video.
        :param title: Display title.
        """

        if stream_url.startswith("/"):
            full_url = f"{self._base_url()}{stream_url}"
        else:
            full_url = stream_url

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8" />
          <title>{title}</title>
          <style>
            body {{
              margin: 0;
              padding: 12px;
              background: #111;
              color: #f5f5f5;
              font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}
            .wrap {{
              max-width: 960px;
              margin: 0 auto;
            }}
            h3 {{
              margin: 0 0 10px 0;
              font-size: 16px;
              font-weight: 600;
            }}
            video {{
              width: 100%;
              max-height: 70vh;
              border-radius: 12px;
              background: black;
            }}
            a {{
              color: #93c5fd;
              font-size: 13px;
            }}
          </style>
        </head>
        <body>
          <div class="wrap">
            <h3>{title}</h3>
            <video controls playsinline preload="metadata">
              <source src="{full_url}" type="video/mp4">
              Your browser does not support the video tag.
            </video>
            <p><a href="{full_url}" target="_blank">Open video directly</a></p>
          </div>
        </body>
        </html>
        """

        return HTMLResponse(
            content=html,
            headers={"Content-Disposition": "inline"},
        )

    def create_wait_download_and_render_sora_video(
        self,
        prompt: str,
        model: str = "sora-2",
        size: str = "1280x720",
        seconds: str = "8",
        __user__: Optional[dict] = None,
    ) -> tuple[HTMLResponse, dict]:
        """
        Create a Sora video, poll until completed, download it to PlexIntel storage,
        and render the video player in OpenWebUI.

        Use this only when the user explicitly wants to wait for the video.
        For longer jobs, prefer create_sora_video + get_sora_video_status + download_sora_video.
        """

        created = self.create_sora_video(
            prompt=prompt,
            model=model or self.valves.DEFAULT_MODEL,
            size=size or self.valves.DEFAULT_SIZE,
            seconds=str(seconds or self.valves.DEFAULT_SECONDS),
            __user__=__user__,
        )
        video_id = created["id"]

        for _ in range(self.valves.MAX_POLLS):
            status = self.get_sora_video_status(video_id)
            state = status.get("status")

            if state == "completed":
                stored = self._download_sora_video_payload(video_id, __user__=__user__)
                stream_url = stored.get("stream_url")
                if not stream_url:
                    raise RuntimeError(f"Video completed but no stream_url returned: {stored}")

                embed = self.render_sora_video(
                    stream_url=stream_url,
                    title=f"Sora video: {video_id}",
                )
                return embed, stored

            if state == "failed":
                raise RuntimeError(f"Sora video failed: {status}")

            time.sleep(self.valves.POLL_SECONDS)

        raise TimeoutError(f"Sora video did not complete after polling: {video_id}")
```

## Enable In OpenWebUI

1. Go to `Workspace` -> `Tools`.
2. Create/import the tool above.
3. Open the tool settings and set `PLEXINTEL_BASE_URL` to the externally reachable PlexIntel URL.
4. Give your user or group access to the tool.
5. Either attach it to a model under `Workspace` -> `Models`, or enable it from the chat `+` menu.
6. Set Function Calling to `Native` for the model or chat.

If you previously imported an older version of this tool, replace the tool code with this version. The
important change is that `download_sora_video` now returns an inline `HTMLResponse`, not just JSON.
OpenWebUI renders that response as an embedded iframe in the chat.

## Quick Test Prompts

Use this first to avoid waiting:

```text
Create a Sora video job for: a cinematic shot of a golden retriever running through autumn leaves. Use 8 seconds.
```

Then poll:

```text
Check the status of video_...
```

When completed:

```text
Download and render video_...
```

The model may still call this tool as `download_sora_video`; that is okay. In this version,
`download_sora_video` stores the MP4 and embeds the video player.

If you want the whole workflow in one call:

```text
Generate and wait for a Sora video of a neon-lit train station at night, 8 seconds, then render it here.
```

## Troubleshooting

- `403` or `404`: verify the PlexIntel public URL and reverse proxy route.
- `503`: PlexIntel cannot see `OPENAI_API_KEY` or the OpenAI SDK is not installed in the runtime environment.
- `409`: the Sora job is still queued or in progress; poll again later.
- Video does not play: open the returned `stream_url` directly from a browser on the NAS/client machine.
- Files missing later: cleanup deletes files after `SORA_RETENTION_HOURS`, default 24.
