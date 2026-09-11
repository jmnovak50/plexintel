"""Optional cross-check against the actual patched OpenWebUI content helpers."""

import base64
import importlib.util
import json
import os
from pathlib import Path

import pytest
from mcp.types import CallToolResult

from app.mcp.tools.assets import _image_content


@pytest.mark.asyncio
async def test_native_wire_to_vision_storage_and_final_attachment(tmp_path):
    checkout = os.environ.get("OPENWEBUI_CHECKOUT")
    if not checkout:
        pytest.skip("Set OPENWEBUI_CHECKOUT to verify the patched OpenWebUI checkout")
    path = Path(checkout) / "backend/open_webui/utils/mcp/content.py"
    spec = importlib.util.spec_from_file_location("openwebui_content_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Public synthetic 1x1 PNG; no user image or identity is involved.
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF9sAAAAASUVORK5CYII="
    )
    wire = CallToolResult(content=[_image_content(raw, "image/png")]).model_dump(mode="json", by_alias=True)
    text, images = module.normalize_tool_result_images(wire["content"], "get_asset_thumbnail", "mcp")
    writes = []

    async def persist(uri):
        output = tmp_path / "persisted.png"
        output.write_bytes(base64.b64decode(uri.split(",", 1)[1]))
        writes.append(output)
        return "/api/v1/files/one/content"

    vision, display = await module.prepare_response_tool_files(images, persist)
    output = [
        {"type": "function_call_output", "output": [{"type": "input_text", "text": text}], "files": display}
    ]
    assistant, added = module.merge_response_tool_images_into_assistant_files(output)
    again, duplicate = module.merge_response_tool_images_into_assistant_files(output, assistant)
    _, reused = await module.prepare_response_tool_files(assistant, persist)
    assert len(writes) == 1 and writes[0].read_bytes() == raw
    assert vision == [{"type": "input_image", "image_url": images[0]["url"]}]
    assert assistant == added == again == reused == display
    assert duplicate == []
    assert "base64" not in json.dumps({"output": output, "files": assistant})
