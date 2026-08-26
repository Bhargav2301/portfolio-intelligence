from __future__ import annotations

from copy import deepcopy
from threading import RLock

from .models import AnalysisRun, RunEvent


class InMemoryRunStore:
    """Test-release store. Replace with Postgres + Redis Streams for production."""

    def __init__(self) -> None:
        self._runs: dict[str, AnalysisRun] = {}
        self._events: dict[str, list[RunEvent]] = {}
        self._lock = RLock()

    def create(self, run: AnalysisRun) -> AnalysisRun:
        with self._lock:
            self._runs[run.id] = deepcopy(run)
            self._events[run.id] = []
            return deepcopy(run)

    def get(self, run_id: str) -> AnalysisRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None

    def save(self, run: AnalysisRun) -> AnalysisRun:
        with self._lock:
            self._runs[run.id] = deepcopy(run)
            return deepcopy(run)

    def append_event(self, run_id: str, event: RunEvent) -> None:
        with self._lock:
            self._events.setdefault(run_id, []).append(deepcopy(event))

    def events(self, run_id: str, after: int = 0) -> list[RunEvent]:
        with self._lock:
            return [
                deepcopy(event)
                for event in self._events.get(run_id, [])
                if event.sequence > after
            ]

    def latest_for_owner(self, owner_email: str) -> AnalysisRun | None:
        with self._lock:
            matches = [
                run for run in self._runs.values() if run.owner_email == owner_email
            ]
            if not matches:
                return None
            return deepcopy(max(matches, key=lambda run: run.created_at))
