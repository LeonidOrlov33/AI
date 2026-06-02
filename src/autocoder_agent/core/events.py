from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import Stage


@dataclass(slots=True)
class AgentEvent:
    stage: Stage
    message: str
    payload: Any = None


EventCallback = Callable[[AgentEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[EventCallback] = []

    def subscribe(self, callback: EventCallback) -> None:
        self._subscribers.append(callback)

    def emit(self, stage: Stage, message: str, payload: Any = None) -> None:
        event = AgentEvent(stage=stage, message=message, payload=payload)
        for callback in list(self._subscribers):
            callback(event)
