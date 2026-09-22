"""Static safety and orchestration contract for the managed OpenWebUI prompt."""

from pathlib import Path

PROMPT = Path(__file__).resolve().parents[1] / "openwebui/system-prompt.txt"


def prompt_text() -> str:
    return PROMPT.read_text(encoding="utf-8")


def test_prompt_requires_compound_constraints_and_active_album_scope():
    text = prompt_text()
    assert "active album remains mandatory" in text
    assert "every named album, person, capture location, date, media type, and requested" in text
    assert "use search_library for compound requests" in text
    assert "Never use\nsearch_location_assets" in text
    assert "Zero\nintersection matches means zero" in text


def test_prompt_requires_identity_evidence_and_visual_review_for_ranking():
    text = prompt_text()
    assert "returned\nImmich person evidence or successful visual inspection" in text
    assert "Missing people metadata does not prove" in text
    assert "inspect candidates\nsequentially before ranking" in text
    assert "Reject near-duplicate" in text
    assert "not an exhaustive visual review" in text


def test_prompt_defines_all_results_and_display_limits():
    text = prompt_text()
    assert "complete=true" in text
    assert "Report the verified metadata match count" in text
    assert "Display at most three" in text
    assert "displayed subset" in text
    assert "unless\ncompleted enumeration found exactly three" in text


def test_prompt_preserves_parent_chat_attachment_security_contract():
    text = prompt_text()
    assert "visible parent\nchat" in text
    assert "Subagents may perform bounded metadata discovery only" in text
    assert "inspect no more than six photos" in text.lower()
    assert "display_immich_photos once per response" in text
    assert "attached_selection" in text
    assert "get_last_immich_display" in text
    assert "Never claim browser\nrendering" in text
    assert "Never retry a failed inspection or display automatically" in text


def test_prompt_declines_uncontrolled_original_attachment_path():
    text = prompt_text()
    assert "not reliable original/full-resolution attachment" in text
    assert "do not call\nget_asset_image" in text
    assert "do not" in text and "expose a download path" in text
