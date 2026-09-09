from typing import Literal
from psycopg2 import errors
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from api.routes.admin_routes import require_admin
from api.services.dimension_explorer import get_register, get_dimension, get_prediction, STATUS_FILTERS, SORTS
from api.services.dimension_governance import apply_action

router = APIRouter(prefix='/admin/dimensions', dependencies=[Depends(require_admin)])


def scope(username: str | None = None, model_version: str = '',
          media_type: Literal['', 'movie', 'episode', 'show', 'season'] = '',
          top_n: int = Query(100,ge=0,le=10000)):
    return dict(username=username,media_type=media_type,top_n=top_n,model_version=model_version)


def configuration_error(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except errors.QueryCanceled as exc:
        raise HTTPException(503, 'The scope exceeded the query time limit. Reduce top-N or select one user and retry.') from exc
    except errors.UndefinedTable as exc:
        raise HTTPException(503, 'Explorer schema is not ready. Apply the migrations in docs/dimension-explorer.md.') from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('')
def register(search: str = Query('',max_length=200), side: Literal['','media','user'] = '',
             status: str = '', sort: str = 'dimension', offset: int = Query(0,ge=0),
             limit: int = Query(50,ge=1,le=100), active_scope=Depends(scope)):
    if (status and status not in STATUS_FILTERS) or sort not in SORTS:
        raise HTTPException(422,'Unknown filter or sort')
    return configuration_error(get_register,active_scope,search,side,status,sort,offset,limit)


@router.get('/prediction')
def prediction(username: str, rating_key: int, scored_at: str, model_version: str = 'legacy'):
    data = configuration_error(get_prediction,username,rating_key,scored_at,model_version)
    if data is None:
        raise HTTPException(404,'Current prediction not found')
    return data


@router.get('/{dimension}')
def dimension_detail(dimension: int, offset: int = Query(0,ge=0), limit: int = Query(25,ge=1,le=100),
                     history_offset: int = Query(0,ge=0), active_scope=Depends(scope)):
    return configuration_error(get_dimension,dimension,active_scope,offset,limit,history_offset)


class ActionRequest(BaseModel):
    config_id: str
    version: int = Field(ge=0)
    action: Literal['review','pause','resume','suppress','restore','investigate','clear']
    reason: str = Field(min_length=1,max_length=2000)


@router.post('/{dimension}/actions')
def intervention(dimension: int, body: ActionRequest, admin=Depends(require_admin)):
    return configuration_error(apply_action,body.config_id,dimension,admin['username'],body.action,body.reason,body.version)
