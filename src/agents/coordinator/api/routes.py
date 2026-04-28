from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agents.coordinator.application.service import (
    CoordinatorService,
    OrderNotFound,
    TaskCallbackNotAllowed,
    TaskNotFound,
    TaskOrderMismatch,
)
from app.config.container import AppContainer, get_container
from shared.contracts.orders import CreateOrderRequest, OrderResponse
from shared.contracts.tasks import TaskCompletedRequest
from shared.contracts.trace import TraceEvent

router = APIRouter(tags=["coordinator"])


def get_coordinator(container: AppContainer = Depends(get_container)) -> CoordinatorService:
    return container.coordinator


def to_order_response(order) -> OrderResponse:
    return OrderResponse(
        order_id=order.order_id,
        source_id=order.source_id,
        correlation_id=order.correlation_id,
        status=order.status.value,
        attempts=order.attempts,
        cr_task_ids=order.cr_task_ids,
        replica_started=order.replica_started,
    )


@router.post("/order", response_model=OrderResponse)
async def create_order(
    request: CreateOrderRequest,
    coordinator: CoordinatorService = Depends(get_coordinator),
) -> OrderResponse:
    order = await coordinator.create_order(request)
    return to_order_response(order)


@router.get("/order/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    coordinator: CoordinatorService = Depends(get_coordinator),
) -> OrderResponse:
    try:
        order = await coordinator.get_order(order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc
    return to_order_response(order)


@router.post("/order/{order_id}/task-completed", response_model=OrderResponse)
async def task_completed(
    order_id: str,
    request: TaskCompletedRequest,
    coordinator: CoordinatorService = Depends(get_coordinator),
) -> OrderResponse:
    try:
        order = await coordinator.handle_task_completed(order_id, request)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc
    except TaskNotFound as exc:
        raise HTTPException(status_code=404, detail="CR task not found") from exc
    except TaskOrderMismatch as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TaskCallbackNotAllowed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_order_response(order)


@router.get("/trace/{correlation_id}", response_model=list[TraceEvent])
async def get_trace(
    correlation_id: str,
    coordinator: CoordinatorService = Depends(get_coordinator),
) -> list[TraceEvent]:
    return await coordinator.list_trace(correlation_id)
