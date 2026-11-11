# label_embeddings.py
# Summarize and label embedding dimensions using a configurable LLM provider.

from dotenv import load_dotenv

load_dotenv()

import argparse
from contextlib import closing

from api.services.dimension_governance import dimension_review_guard, record_assessment
from api.db.connection import connect_db
from gpt_utils import (
    UNCLEAR_LABEL,
    build_dimension_prompt,
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


def label_single_dimension(dimension, top_n=10, generate_label=False, save_label=False,
                           label_provider=None, label_model=None):
    from api.services.dimension_label_batch import main as current_main
    argv=['--dimension',str(dimension),'--top-n',str(top_n)]
    if generate_label:argv.append('--label')
    if save_label:argv.append('--save-label')
    if label_provider:argv.extend(['--label-provider',label_provider])
    if label_model:argv.extend(['--label-model',label_model])
    return current_main(argv)


def main(argv=None):
    from api.services.dimension_label_batch import main as current_main
    return current_main(argv)


if __name__=='__main__':
    main()
