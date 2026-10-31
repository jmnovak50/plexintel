"""Administrator-only eligibility reads and same-origin, explicitly enabled writes."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from api.routes.admin_routes import require_admin
from api.services import eligibility_workspace as workspace
from api.services.global_eligibility import Policy

router = APIRouter(prefix='/admin/eligibility', dependencies=[Depends(require_admin)])


def action(request: Request):
    from urllib.parse import urlsplit
    try:
        origin = urlsplit(request.headers.get('origin', ''))
    except ValueError:
        raise HTTPException(403, 'Invalid action origin') from None
    if (origin.scheme != request.url.scheme or origin.netloc != request.url.netloc or
            request.headers.get('x-eligibility-action') != '1' or
            request.headers.get('sec-fetch-site') == 'cross-site'):
        raise HTTPException(403, 'Same-origin eligibility action required')


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except workspace.EligibilityError as exc:
        raise HTTPException(exc.status, exc.code) from None
    except ValueError:
        raise HTTPException(422, 'invalid_eligibility_parameters') from None
    except Exception:
        # Never serialize connection strings or database exception detail.
        raise HTTPException(503, 'eligibility_unavailable') from None


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)
    policy: Policy


class Evaluation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=0)


@router.get('/overview')
def overview():
    return call(workspace.overview)


@router.get('/policy')
def policy():
    return call(workspace.policy_payload)


@router.put('/policy', dependencies=[Depends(action)])
def save(body: PolicyUpdate, user=Depends(require_admin)):
    return call(workspace.save_policy, body.policy, body.expected_version, user['username'])


@router.post('/preview', dependencies=[Depends(action)])
def preview(body: Policy):
    return call(workspace.preview, body)


@router.post('/evaluations', dependencies=[Depends(action)], status_code=201)
def evaluate(body: Evaluation, user=Depends(require_admin)):
    return call(workspace.run_evaluation, body.expected_version, user['username'])


@router.get('/evaluations')
def history(page: int = Query(1, ge=1, le=100000), limit: int = Query(25, ge=1, le=100)):
    return call(workspace.history, page, limit)


@router.get('/results')
def results(run_id: UUID | None = None, page: int = Query(1, ge=1, le=100000),
            limit: int = Query(25, ge=1, le=100), search: str = Query('', max_length=200),
            outcome: Literal['retained', 'excluded'] | None = None,
            media_type: Literal['movie', 'tv'] | None = None, incomplete: bool = False,
            sort: Literal['title', 'tmdb_id', 'outcome', 'media_type'] = 'title',
            direction: Literal['asc', 'desc'] = 'asc'):
    return call(workspace.results, run_id, page=page, limit=limit, search=search,
                outcome=outcome, media_type=media_type, incomplete=incomplete, sort=sort, direction=direction)
