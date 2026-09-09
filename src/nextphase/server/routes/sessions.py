from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from nextphase.server.deps import get_store
from nextphase.server.schemas import (
    BaselineOut,
    EventOut,
    MetricPointOut,
    SessionOut,
    SessionSummaryOut,
)
from nextphase.store.base import AbstractStore, MetricCategory

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummaryOut])
def list_sessions(
    model_name: str | None = None, store: AbstractStore = Depends(get_store)
) -> list[SessionSummaryOut]:
    out = []
    for s in store.list_sessions(model_name=model_name):
        latest_event = store.query_events(s.session_id, limit=1)
        open_alerts = store.query_alerts(s.session_id, status="open")
        event_count = len(store.query_events(s.session_id, limit=100_000))
        out.append(
            SessionSummaryOut(
                session_id=s.session_id,
                model_name=s.model_name,
                modality=s.modality,
                created_at=s.created_at,
                tracking_uri=s.tracking_uri,
                metadata=s.metadata,
                status=s.status,
                event_count=event_count,
                last_event_at=latest_event[0].timestamp if latest_event else None,
                open_alert_count=len(open_alerts),
            )
        )
    return out


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, store: AbstractStore = Depends(get_store)) -> SessionOut:
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(**vars(session))


@router.get("/{session_id}/baseline", response_model=BaselineOut)
def get_baseline(session_id: str, store: AbstractStore = Depends(get_store)) -> BaselineOut:
    baseline = store.get_baseline(session_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="No baseline logged for this session")
    return BaselineOut(
        baseline_id=baseline.baseline_id,
        session_id=baseline.session_id,
        created_at=baseline.created_at,
        row_count=baseline.row_count,
        column_schema=baseline.schema,
        summary_stats=baseline.summary_stats,
    )


@router.get("/{session_id}/events", response_model=list[EventOut])
def get_events(
    session_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    store: AbstractStore = Depends(get_store),
) -> list[EventOut]:
    events = store.query_events(session_id, start=start, end=end, limit=limit, offset=offset)
    return [EventOut(**vars(e)) for e in events]


@router.get("/{session_id}/metrics", response_model=list[MetricPointOut])
def get_metrics(
    session_id: str,
    category: MetricCategory | None = None,
    metric_name: str | None = None,
    feature_name: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    store: AbstractStore = Depends(get_store),
) -> list[MetricPointOut]:
    metrics = store.query_metrics(
        session_id,
        metric_name=metric_name,
        category=category,
        feature_name=feature_name,
        start=start,
        end=end,
    )
    return [MetricPointOut(**vars(m)) for m in metrics]
