from __future__ import annotations

from uuid import uuid4

from app.schemas.api import AnalyzeRequest
from app.schemas.graph_state import TradePilotState


def validate_request(state: TradePilotState | dict) -> TradePilotState:
    incoming_state = _prepare_state_payload(state)
    validated_state = TradePilotState.model_validate(incoming_state)

    normalized_ticker = validated_state.request.ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError("request ticker must not be blank after normalization")

    return validated_state.model_copy(
        update={
            "request": AnalyzeRequest(ticker=normalized_ticker),
            "normalized_ticker": normalized_ticker,
            "request_id": _resolve_request_id(validated_state.request_id),
        }
    )


def _prepare_state_payload(state: TradePilotState | dict) -> dict:
    if isinstance(state, TradePilotState):
        payload = state.model_dump(mode="python")
    else:
        payload = dict(state)

    request_payload = payload.get("request")
    ticker = request_payload.get("ticker") if isinstance(request_payload, dict) else None
    if isinstance(ticker, str) and not ticker.strip():
        raise ValueError("request ticker must not be blank after normalization")

    payload["request_id"] = _resolve_request_id(payload.get("request_id"))
    return payload


def _resolve_request_id(request_id: object) -> str:
    if isinstance(request_id, str) and request_id.strip():
        return request_id

    return str(uuid4())
