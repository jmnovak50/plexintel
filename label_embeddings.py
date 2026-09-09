# label_embeddings.py
# Summarize and label embedding dimensions using a configurable LLM provider.

from dotenv import load_dotenv

load_dotenv()

import argparse
from contextlib import closing

from api.db.schema import ensure_app_schema
from api.services.dimension_governance import dimension_review_guard, record_assessment
from api.db.connection import connect_db
from gpt_utils import (
    UNCLEAR_LABEL,
    build_dimension_prompt,
    call_llm_for_label_result,
    get_dimension_mode,
    get_bottom_media_for_dimension,
    get_bottom_users_for_dimension,
    get_media_metadata,
    get_top_media_for_dimension,
    get_top_users_for_dimension,
    get_user_positive_training_examples,
    insert_label,
    resolve_label_backend,
)


def _should_persist_label(label: str) -> bool:
    return bool(label and label != UNCLEAR_LABEL)


def _format_result_metadata(result: dict) -> str:
    details = []
    confidence = result.get("label_confidence")
    label_type = result.get("label_type")
    if confidence:
        details.append(f"confidence={confidence}")
    if label_type:
        details.append(f"type={label_type}")

    high_count = result.get("coverage_high_count")
    high_total = result.get("coverage_high_total")
    high_percent = result.get("coverage_high_percent")
    if high_count is not None and high_total is not None:
        coverage = f"HIGH coverage={high_count}/{high_total}"
        if high_percent is not None:
            coverage += f" ({high_percent}%)"
        details.append(coverage)

    low_count = result.get("coverage_low_overlap_count")
    low_total = result.get("coverage_low_total")
    low_percent = result.get("coverage_low_overlap_percent")
    if low_count is not None and low_total is not None:
        overlap = f"LOW overlap={low_count}/{low_total}"
        if low_percent is not None:
            overlap += f" ({low_percent}%)"
        details.append(overlap)

    validation_status = result.get("validation_status")
    if validation_status:
        details.append(f"validation={validation_status}")

    return " | ".join(details)


def _format_validation_notes(notes) -> str:
    if isinstance(notes, list):
        return " | ".join(str(note) for note in notes if str(note).strip())
    return str(notes or "")


def _fetch_dimension_samples(dimension: int, top_n: int):
    if get_dimension_mode(dimension) == "media":
        positive_ids = get_top_media_for_dimension(dimension, top_n=top_n)
        negative_ids = get_bottom_media_for_dimension(dimension, top_n=top_n)
        return "media", get_media_metadata(positive_ids), get_media_metadata(negative_ids)

    positive_ids = get_top_users_for_dimension(dimension, top_n=top_n)
    negative_ids = get_bottom_users_for_dimension(dimension, top_n=top_n)
    return (
        "user",
        get_user_positive_training_examples(positive_ids),
        get_user_positive_training_examples(negative_ids),
    )


def _label_single_dimension(
    dimension,
    top_n=10,
    generate_label=False,
    save_label=False,
    label_provider=None,
    label_model=None,
    assessment_context=None,
):
    context = assessment_context if assessment_context is not None else {}
    mode, positive_df, negative_df = _fetch_dimension_samples(dimension, top_n)
    prompt_bundle = build_dimension_prompt(
        dimension,
        positive_df,
        negative_df,
        dimension_mode=mode,
    )

    context['prompt'] = prompt_bundle

    print(f"📄 Prompt for label generation ({mode} dim {dimension}):")
    print(prompt_bundle["prompt_text"])

    if prompt_bundle["skipped_reason"]:
        context.update(result={'validation_status': 'invalid', 'validation_notes': [prompt_bundle['skipped_reason']]}, outcome='insufficient_evidence')
        print(f"⚠️ {UNCLEAR_LABEL}: {prompt_bundle['skipped_reason']}")
        return

    if generate_label:
        provider_name, model_name = resolve_label_backend(label_provider, label_model)
        result = call_llm_for_label_result(
            prompt_bundle["prompt_text"],
            provider=provider_name,
            model=model_name,
            dimension_mode=mode,
        )
        context.update(result=result,provider=provider_name,model=model_name,outcome='candidate_not_saved')
        print(f"🧠 Suggested label for dim {dimension} via {provider_name}:{model_name}: {result['label']}")
        result_metadata = _format_result_metadata(result)
        if result_metadata:
            print(f"   {result_metadata}")
        validation_notes = _format_validation_notes(result.get("validation_notes", []))
        if validation_notes:
            print(f"   Validation: {validation_notes}")
        if result.get("explanation"):
            print(f"   {result['explanation']}")
        for evidence in result.get("evidence", []):
            if evidence:
                print(f"   - {evidence}")
        if (
            save_label
            and result.get("validation_status") != "invalid"
            and _should_persist_label(result["label"])
        ):
            insert_label(dimension, result["label"])
            context.update(saved=True,outcome="legacy_single_label_saved")


def label_single_dimension(dimension, top_n=10, generate_label=False, save_label=False,
                           label_provider=None, label_model=None):
    with closing(connect_db()) as conn, conn:
        with conn.cursor() as cur:
            with dimension_review_guard(cur, dimension) as allowed:
                if not allowed:
                    print(f"Dimension {dimension}: paused or already running; skipped")
                    return
                cur.execute('SELECT row_to_json(el) FROM embedding_labels el WHERE dimension=%s LIMIT 1',(dimension,))
                existing = cur.fetchone()
                context = {}
                value = _label_single_dimension(dimension,top_n=top_n,generate_label=generate_label,
                    save_label=save_label,label_provider=label_provider,label_model=label_model,assessment_context=context)
                if generate_label and save_label:
                    cur.execute('SELECT row_to_json(el) FROM embedding_labels el WHERE dimension=%s LIMIT 1',(dimension,))
                    current = cur.fetchone()
                    record_assessment(cur,dimension,source='single-cli',provider=context.get('provider'),
                        model=context.get('model'),prompt=context.get('prompt',{}),result=context.get('result',{}),
                        saved=context.get('saved',False),outcome=context.get('outcome','no_label_saved'),
                        before=existing[0] if existing else None,after=current[0] if current else None)
                    conn.commit()
                return value


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dimension", type=int, help="Single embedding dimension index")
    group.add_argument("--dimensions", nargs="+", type=int, help="List of embedding dimension indexes")
    parser.add_argument("--top_n", type=int, default=10, help="Number of ranked items or users to inspect per side")
    parser.add_argument("--label", action="store_true", help="Generate a label using the configured LLM provider")
    parser.add_argument("--gpt_label", dest="label", action="store_true", help="Deprecated alias for --label")
    parser.add_argument("--label_provider", choices=["openai", "ollama"], default=None, help="Override label provider")
    parser.add_argument("--label_model", default=None, help="Override label model name")
    parser.add_argument("--save_label", action="store_true", help="Store the label in the embedding_labels table")
    args = parser.parse_args()

    dimensions = args.dimensions if args.dimensions else [args.dimension]

    for dim in dimensions:
        label_single_dimension(
            dim,
            top_n=args.top_n,
            generate_label=args.label,
            save_label=args.save_label,
            label_provider=args.label_provider,
            label_model=args.label_model,
        )


if __name__ == "__main__":
    ensure_app_schema()
    main()
