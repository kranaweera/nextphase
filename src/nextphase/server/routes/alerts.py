from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from nextphase.server.deps import get_store
from nextphase.server.schemas import AlertOut, AlertRuleIn, AlertRuleOut
from nextphase.store.base import AbstractStore, AlertRule, AlertStatus

router = APIRouter(tags=["alerts"])


@router.get("/alert-rules", response_model=list[AlertRuleOut])
def list_alert_rules(
    session_id: str | None = None, store: AbstractStore = Depends(get_store)
) -> list[AlertRuleOut]:
    return [AlertRuleOut(**vars(r)) for r in store.list_alert_rules(session_id=session_id)]


@router.post("/sessions/{session_id}/alert-rules", response_model=AlertRuleOut)
def create_alert_rule(
    session_id: str, rule_in: AlertRuleIn, store: AbstractStore = Depends(get_store)
) -> AlertRuleOut:
    rule = AlertRule(
        rule_id=str(uuid.uuid4()),
        session_id=session_id,
        metric_name=rule_in.metric_name,
        feature_name=rule_in.feature_name,
        comparator=rule_in.comparator,
        threshold=rule_in.threshold,
        window=rule_in.window,
        consecutive_windows=rule_in.consecutive_windows,
        enabled=rule_in.enabled,
        notifiers=rule_in.notifiers,
        created_at=datetime.now(timezone.utc),
    )
    store.create_alert_rule(rule)
    return AlertRuleOut(**vars(rule))


@router.delete("/alert-rules/{rule_id}")
def delete_alert_rule(rule_id: str, store: AbstractStore = Depends(get_store)) -> dict[str, str]:
    store.delete_alert_rule(rule_id)
    return {"status": "deleted"}


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    session_id: str | None = None,
    status: AlertStatus | None = None,
    store: AbstractStore = Depends(get_store),
) -> list[AlertOut]:
    return [AlertOut(**vars(a)) for a in store.query_alerts(session_id=session_id, status=status)]


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: str, store: AbstractStore = Depends(get_store)) -> dict[str, str]:
    store.ack_alert(alert_id)
    return {"status": "acknowledged"}
