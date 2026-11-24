"""Consumer presentation uses structured evidence without redefining legacy fields."""
import json
from unittest.mock import patch

from api.services import digest_service as d,agent_tool_service as a
from openwebui_pipelines.plexintel_recommendation_pipeline import Pipeline
from tests.test_agent_tool_service import FakeConnection

LEGACY='Legacy inferred viewer preference'
FACT='You liked an episode of Series A. The series shares a director.'
ROW=dict(rating_key=1,title='Film B',media_type='movie',predicted_probability=.91,
         title_traits=['Existing title trait'],semantic_themes=LEGACY,
         viewing_history_connection={'display_text':FACT})


def test_agent_keeps_legacy_payload_and_exposes_both_presentations():
    with patch.object(a,'_get_conn',return_value=FakeConnection([ROW])),patch.object(a,'attach_viewing_connections'):
        response=a.get_agent_recommendations(user='fixture')
    item=response.items[0]
    assert item.explanation==LEGACY and item.title_traits==['Existing title trait']
    assert item.viewing_history_connection=={'display_text':FACT} and item.score==.91


def test_digest_html_and_plain_text_use_factual_taste_match_and_keep_traits():
    html=d._render_item_card(ROW)
    assert LEGACY not in html and 'Connections to Your Viewing History' not in html
    assert 'Title Traits' in html and 'Existing title trait' in html and 'Taste Match' in html and FACT in html
    assert '#065f46' in html
    text=d._render_digest_text(recipient_user={'username':'fixture'},rendered_for_user={'username':'fixture'},
        preference_row={'unsubscribe_token':'fixture'},message_html='',digest_settings={'base_url':'https://example.invalid'},
        movies=[ROW],shows=[],subject='Fixture digest',is_test=False)
    assert LEGACY not in text and 'Taste Match: '+FACT in text and 'Title Traits: Existing title trait' in text


def test_digest_missing_connection_has_no_legacy_fallback_and_escapes_text():
    assert 'Taste Match' not in d._render_item_card(dict(ROW,viewing_history_connection=None))
    html=d._render_item_card(dict(ROW,viewing_history_connection={'display_text':'Watched <script> & series'}))
    assert '&lt;script&gt; &amp; series' in html and '<script>' not in html


def test_openwebui_format_uses_factual_context_without_legacy_fallback():
    pipeline=Pipeline()
    row=dict(ROW,score=.91,explanation=LEGACY,summary='Content synopsis.')
    rendered='\n'.join(pipeline._format_ranked_item(1,row))
    assert 'Taste Match: '+FACT in rendered and 'Title Traits: Existing title trait' in rendered
    assert 'Summary: Content synopsis.' in rendered and LEGACY not in rendered and 'Why:' not in rendered
    assert 'score `91%`' in rendered
    absent='\n'.join(pipeline._format_ranked_item(1,dict(row,viewing_history_connection=None)))
    assert 'Taste Match' not in absent and LEGACY not in absent


def test_optional_narration_does_not_receive_legacy_labels_or_private_connection():
    pipeline=Pipeline();pipeline.valves.ENABLE_GEMMA_NARRATION=True
    pipeline.valves.OLLAMA_BASE_URL='http://fixture.invalid';pipeline.valves.OLLAMA_MODEL='fixture'
    calls=[]
    def post(path,payload):calls.append(payload);return {'message':{'content':'A content summary.'}}
    pipeline._ollama_post=post
    pipeline._call_gemma_narration(prompt='Recommend a film',username='fixture',view='movies',items=[dict(ROW,explanation=LEGACY)])
    payload=json.dumps(calls)
    assert calls and LEGACY not in payload and FACT not in payload
