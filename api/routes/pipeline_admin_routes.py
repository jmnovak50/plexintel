from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.routes.admin_routes import require_admin
from api.services.pipeline_service import (
    get_pipeline_run,
    get_pipeline_runs,
    run_pipeline,
)

router = APIRouter()


def _serialize_run(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("started_at", "completed_at"):
        v = out.get(key)
        if v is not None and hasattr(v, "isoformat"):
            out[key] = v.isoformat()
    stages = out.get("stages")
    if isinstance(stages, list):
        out["stages"] = [_serialize_stage(s) for s in stages]
    return out


def _serialize_stage(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("started_at", "completed_at"):
        v = out.get(key)
        if v is not None and hasattr(v, "isoformat"):
            out[key] = v.isoformat()
    return out


@router.get("/admin/pipeline/runs")
def admin_list_pipeline_runs(
    limit: int = Query(50, ge=1, le=200),
    admin_user=Depends(require_admin),
):
    payload = get_pipeline_runs(limit=limit)
    runs = [_serialize_run(r) for r in payload.get("runs", [])]
    return {"requested_by": admin_user["username"], "runs": runs}


@router.get("/admin/pipeline/runs/{run_id}")
def admin_get_pipeline_run(run_id: int, admin_user=Depends(require_admin)):
    row = get_pipeline_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"requested_by": admin_user["username"], "run": _serialize_run(row)}


@router.post("/admin/pipeline/trigger")
def admin_trigger_pipeline(admin_user=Depends(require_admin)):
    username = admin_user["username"]

    def worker() -> None:
        try:
            run_pipeline(
                delivery_type="manual",
                triggered_by=username,
                schedule_key=None,
            )
        except Exception as exc:
            print(f"Manual pipeline error: {exc}")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return {
        "status": "accepted",
        "requested_by": username,
        "detail": "Pipeline started in the background. Refresh runs to see progress.",
    }
