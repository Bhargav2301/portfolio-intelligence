from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import uuid4

from .engine import AnalysisEngine, TradingAgentsEngine
from .models import (
    AnalysisRun,
    AnalysisRunRequest,
    EventLevel,
    RunEvent,
    RunStatus,
    utc_now,
)
from .policy import is_blocked, readiness_checks
from .store import InMemoryRunStore
from .workflow import LangGraphPortfolioWorkflow

WorkflowFactory = Callable[..., LangGraphPortfolioWorkflow]


@dataclass
class RunCoordinator:
    store: InMemoryRunStore
    engine: AnalysisEngine
    workflow_factory: WorkflowFactory = field(default=LangGraphPortfolioWorkflow)

    @classmethod
    def production_default(cls) -> "RunCoordinator":
        return cls(store=InMemoryRunStore(), engine=TradingAgentsEngine())

    def create(self, owner_email: str, request: AnalysisRunRequest) -> AnalysisRun:
        checks = readiness_checks(request)
        selected = request.selected_symbols or [holding.symbol for holding in request.holdings]
        status = RunStatus.BLOCKED if is_blocked(checks) else RunStatus.QUEUED
        run = AnalysisRun(
            id=str(uuid4()),
            owner_email=owner_email,
            portfolio_id=request.portfolio_id,
            snapshot_id=request.snapshot_id,
            snapshot_hash=request.snapshot_hash,
            mode=request.mode,
            status=status,
            created_at=utc_now(),
            selected_symbols=selected,
            policy_checks=checks,
        )
        self.store.create(run)
        self._event(run, EventLevel.WARNING if status == RunStatus.BLOCKED else EventLevel.INFO,
                    "policy", "Readiness checks blocked this run" if status == RunStatus.BLOCKED else "Run accepted")
        return self.store.get(run.id) or run

    async def execute(self, run_id: str, request: AnalysisRunRequest) -> None:
        run = self.store.get(run_id)
        if not run or run.status == RunStatus.BLOCKED:
            return
        run.status = RunStatus.RUNNING
        run.started_at = utc_now()
        self.store.save(run)
        self._event(run, EventLevel.INFO, "orchestrator", "Portfolio snapshot locked for analysis")

        try:
            def report(stage: str, message: str, event_symbol: str | None = None) -> None:
                current = self.store.get(run_id)
                if current:
                    self._event(current, EventLevel.INFO, stage, message, event_symbol)

            def persist_result(result) -> None:
                current = self.store.get(run_id)
                if current:
                    current.results.append(result)
                    self.store.save(current)

            workflow = self.workflow_factory(self.engine, report, persist_result)
            self._event(run, EventLevel.INFO, "langgraph", "PI portfolio workflow started")
            await asyncio.to_thread(workflow.invoke, request, run.selected_symbols)

            run = self.store.get(run_id) or run
            run.status = RunStatus.COMPLETED
            run.completed_at = utc_now()
            self.store.save(run)
            self._event(run, EventLevel.INFO, "langgraph", "PI portfolio workflow completed")
        except Exception as error:
            run = self.store.get(run_id) or run
            run.status = RunStatus.FAILED
            run.completed_at = utc_now()
            run.error = f"{type(error).__name__}: analysis failed"
            self.store.save(run)
            self._event(run, EventLevel.ERROR, "orchestrator", run.error)

    def _event(self, run: AnalysisRun, level: EventLevel, stage: str, message: str, symbol: str | None = None) -> None:
        current = self.store.get(run.id) or run
        sequence = current.last_event_sequence + 1
        current.last_event_sequence = sequence
        self.store.save(current)
        self.store.append_event(run.id, RunEvent(
            sequence=sequence,
            occurred_at=utc_now(),
            level=level,
            stage=stage,
            message=message,
            symbol=symbol,
        ))
