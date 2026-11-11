"""Fail-closed operational checks. No receipt registration or import-time I/O."""
from .contracts import ContractError
from .features import SUPERVISION_POLICY
from .recovery import IDENTITY_POLICY

SAFETY_VERSION='canonical-pipeline-safety/1.0'
VERIFICATION_ONLY_EXIT=76


class RunFailure(ContractError):
    def __init__(self,code,message,*,retryable=False):
        super().__init__(message)
        self.code=code;self.retryable=retryable


def classify_failure(exc):
    if isinstance(exc,RunFailure):return dict(code=exc.code,retryable=exc.retryable)
    code=getattr(exc,'pgcode',None)
    if code in {'53200','53300','53400','55P03','40001','40P01','57014','57P01'} or code and code.startswith('08'):
        return dict(code='DATABASE_'+code,retryable=True)
    import psycopg2
    if code is None and isinstance(exc,(psycopg2.OperationalError,psycopg2.InterfaceError)):
        message=str(exc).lower()
        # Uncoded OperationalError also covers authentication/configuration
        # failures. Only recognized libpq transport-loss conditions may retry.
        transport=('connection refused','connection timed out','timeout expired',
            'server closed the connection unexpectedly','connection already closed',
            'connection not open','ssl connection has been closed unexpectedly',
            'connection reset by peer')
        if any(value in message for value in transport):
            return dict(code='DATABASE_CONNECTION',retryable=True)
    # Unknown failures, quality failures and receipt/source mismatches need review.
    return dict(code='POLICY_OR_CONTRACT' if isinstance(exc,ContractError) else 'UNCLASSIFIED',retryable=False)


def failure_message(exc):
    if isinstance(exc,ContractError):return str(exc).splitlines()[0][:240]
    return 'Pipeline stopped ('+type(exc).__name__+'); inspect private diagnostics'

