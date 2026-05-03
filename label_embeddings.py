# label_embeddings.py
# Summarize and label embedding dimensions using a configurable LLM provider.

from dotenv import load_dotenv

load_dotenv()

import argparse

from api.db.schema import ensure_app_schema
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
    get_user_watch_history,
    insert_label,
    resolve_label_backend,
)


def _should_persist_label(label: str) -> bool:
    return bool(label and label != UNCLEAR_LABEL)


def _fetch_dimension_samples(dimension: int, top_n: int):
    if get_dimension_mode(dimension) == "media":
        positive_ids = get_top_media_for_dimension(dimension, top_n=top_n)
        negative_ids = get_bottom_media_for_dimension(dimension, top_n=top_n)
        return "media", get_media_metadata(positive_ids), get_media_metadata(negative_ids)

    positive_ids = get_top_users_for_dimension(dimension, top_n=top_n)
    negative_ids = get_bottom_users_for_dimension(dimension, top_n=top_n)
    return "user", get_user_watch_history(positive_ids), get_user_watch_history(negative_ids)


def label_single_dimension(
    dimension,
    top_n=10,
    generate_label=False,
    save_label=False,
    label_provider=None,
    label_model=None,
):
    mode, positive_df, negative_df = _fetch_dimension_samples(dimension, top_n)
    prompt_bundle = build_dimension_prompt(
        dimension,
        positive_df,
        negative_df,
        dimension_mode=mode,
    )

    print(f"📄 Prompt for label generation ({mode} dim {dimension}):")
    print(prompt_bundle["prompt_text"])

    if prompt_bundle["skipped_reason"]:
        print(f"⚠️ {UNCLEAR_LABEL}: {prompt_bundle['skipped_reason']}")
        return

    if generate_label:
        provider_name, model_name = resolve_label_backend(label_provider, label_model)
        result = call_llm_for_label_result(
            prompt_bundle["prompt_text"],
            provider=provider_name,
            model=model_name,
        )
        print(f"🧠 Suggested label for dim {dimension} via {provider_name}:{model_name}: {result['label']}")
        if result.get("explanation"):
            print(f"   {result['explanation']}")
        for evidence in result.get("evidence", []):
            if evidence:
                print(f"   - {evidence}")
        if save_label and _should_persist_label(result["label"]):
            insert_label(dimension, result["label"])


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
