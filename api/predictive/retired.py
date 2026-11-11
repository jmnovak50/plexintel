"""Reject obsolete embedding/model writers; never query migration state."""
from .contracts import ContractError


def assert_legacy_allowed():
    raise ContractError('Legacy numeric writers are retired. Use scripts/predictive_pipeline.py; no fallback encoder or full-history fit is permitted.')
