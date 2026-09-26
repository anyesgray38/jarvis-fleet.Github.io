"""Department-scoped continuous research for the AEGIS second brain.

The brain keeps active memory small: each fetched source becomes a compact
packet, while the complete untrusted source remains in the authenticated
archive. Research is bounded per cycle, deduplicated by content hash, and
records failures instead of pretending that an empty result means no knowledge
exists.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


@dataclass(frozen=True)
class DepartmentPlan:
    department_id: str
    name: str
    manager: str
    topics: tuple[str, ...] = ()
    queries: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    search_command: str = ""
    capabilities: tuple[str, ...] = ()
    cadence_minutes: int = 360
    enabled: bool = True


def load_department_plans(path: str | Path, *, wiki_topics: list[str] = (), web_sources: list[str] = ()) -> tuple[DepartmentPlan, ...]:
    """Load non-secret department research policy and add legacy env inputs."""
    plans: list[DepartmentPlan] = []
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not str(item.get("id", "")).strip():
            continue
        search_command = str(item.get("search_command") or (item.get("queries") or [""])[0]).strip()
        configured_queries = tuple(str(v).strip() for v in item.get("queries", []) if str(v).strip())
        if not configured_queries and search_command:
            configured_queries = (search_command,)
        plans.append(DepartmentPlan(
            department_id=str(item["id"]).strip(),
            name=str(item.get("name") or item["id"]).strip(),
            manager=str(item.get("manager") or "Aegis").strip(),
            topics=tuple(str(v).strip() for v in item.get("topics", []) if str(v).strip()),
            queries=configured_queries,
            urls=tuple(str(v).strip() for v in item.get("urls", []) if str(v).strip()),
            search_command=search_command,
            capabilities=tuple(str(v).strip() for v in item.get("capabilities", []) if str(v).strip()),
            cadence_minutes=max(5, int(item.get("cadence_minutes", 360))),
            enabled=bool(item.get("enabled", True)),
        ))
    if not plans:
        plans = [DepartmentPlan("web-intelligence", "Web Intelligence", "Atlas")]
    # Preserve the existing environment contract by routing old global inputs
    # to the inbound web-intelligence manager.
    if wiki_topics or web_sources:
        first = plans[0]
        plans[0] = DepartmentPlan(
            first.department_id, first.name, first.manager,
            topics=tuple(dict.fromkeys((*first.topics, *wiki_topics))),
            queries=first.queries,
            urls=tuple(dict.fromkeys((*first.urls, *web_sources))),
            search_command=first.search_command,
            capabilities=first.capabilities,
            cadence_minutes=first.cadence_minutes,
            enabled=first.enabled,
        )
    return tuple(plans)


class KnowledgeBrain:
    """Schedule and execute bounded research against a local KnowledgeStore."""

    def __init__(
        self,
        store: Any,
        *,
        plans: tuple[DepartmentPlan, ...],
        wiki_fetcher: Callable[[str], dict[str, Any]],
        web_fetcher: Callable[[str], dict[str, Any]],
        web_searcher: Callable[[str, int], list[dict[str, Any]]],
        max_jobs_per_cycle: int = 4,
        max_search_results: int = 3,
        max_external_calls: int = 4,
        source_refresh_minutes: int = 1440,
    ) -> None:
        self.store = store
        self.plans = plans
        self.wiki_fetcher = wiki_fetcher
        self.web_fetcher = web_fetcher
        self.web_searcher = web_searcher
        self.max_jobs_per_cycle = max(1, min(25, int(max_jobs_per_cycle)))
        self.max_search_results = max(1, min(10, int(max_search_results)))
        self.max_external_calls = max(1, min(25, int(max_external_calls)))
        self.source_refresh_minutes = max(30, int(source_refresh_minutes))
        self._run_lock = threading.Lock()

    def _research_state(self) -> dict[str, Any]:
        return self.store.data.setdefault("research", {"departments": {}, "cycles": []})

    def _due(self, plan: DepartmentPlan, state: dict[str, Any]) -> bool:
        if not plan.enabled:
            return False
        last = state.get("departments", {}).get(plan.department_id, {}).get("last_run_at")
        if not last:
            return True
        try:
            timestamp = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        except ValueError:
            return True
        return _now() >= timestamp + timedelta(minutes=plan.cadence_minutes)

    def due_departments(self) -> list[str]:
        with self.store.lock:
            state = self._research_state()
            return [plan.department_id for plan in self.plans if self._due(plan, state)]

    def run_due_cycle(self, *, force: bool = False) -> dict[str, Any]:
        if not self._run_lock.acquire(blocking=False):
            return {"status": "already_running", "jobs": [], "errors": []}
        try:
            return self._run_cycle(force=force)
        finally:
            self._run_lock.release()

    def _run_cycle(self, *, force: bool) -> dict[str, Any]:
        cycle_id = f"cycle-{_now().strftime('%Y%m%d%H%M%S')}-{id(self) % 10000:04d}"
        jobs: list[tuple[DepartmentPlan, str, str]] = []
        with self.store.lock:
            state = self._research_state()
            plans = [plan for plan in self.plans if plan.enabled and (force or self._due(plan, state))]
        queues: list[tuple[DepartmentPlan, list[tuple[str, str]]]] = []
        for plan in plans:
            queues.append((plan, [("wiki", value) for value in plan.topics] + [("search", value) for value in plan.queries] + [("web", value) for value in plan.urls]))
        # Fairness is part of the research budget: one department's legacy
        # topic list must not starve every other station from growing.
        while queues and len(jobs) < self.max_jobs_per_cycle:
            remaining: list[tuple[DepartmentPlan, list[tuple[str, str]]]] = []
            for plan, queue in queues:
                if queue and len(jobs) < self.max_jobs_per_cycle:
                    kind, value = queue.pop(0)
                    jobs.append((plan, kind, value))
                if queue:
                    remaining.append((plan, queue))
            queues = remaining
        jobs = jobs[: self.max_jobs_per_cycle]
        outcomes: list[dict[str, Any]] = []
        errors: list[str] = []
        external_calls = 0
        pipeline = {"fetch": 0, "reverse_engineer": 0, "verify": 0, "compact": 0, "promote": 0}
        for plan, kind, value in jobs:
            try:
                if kind == "wiki":
                    packet = self.store.ingest_source(self.wiki_fetcher(value), kind="wiki", manager=plan.manager, department=plan.department_id, query=value)
                    pipeline["fetch"] += 1
                    pipeline["reverse_engineer"] += int(bool(packet.get("reverse_engineering")))
                    pipeline["verify"] += int(packet.get("reverse_engineering", {}).get("status") == "verified_for_compaction")
                    pipeline["compact"] += int(bool(packet.get("summary")))
                    pipeline["promote"] += int(packet.get("promotion", {}).get("status") == "promoted_to_active_memory")
                    outcomes.append({"department": plan.department_id, "kind": kind, "value": value, "packet": packet})
                elif kind == "web":
                    if self.store.source_is_fresh(value, self.source_refresh_minutes):
                        outcomes.append({"department": plan.department_id, "kind": kind, "value": value, "cached": True})
                    elif external_calls >= self.max_external_calls:
                        outcomes.append({"department": plan.department_id, "kind": kind, "value": value, "skipped": "external_call_budget"})
                    else:
                        packet = self.store.ingest_source(self.web_fetcher(value), kind="web", manager=plan.manager, department=plan.department_id, query=value)
                        pipeline["fetch"] += 1
                        pipeline["reverse_engineer"] += int(bool(packet.get("reverse_engineering")))
                        pipeline["verify"] += int(packet.get("reverse_engineering", {}).get("status") == "verified_for_compaction")
                        pipeline["compact"] += int(bool(packet.get("summary")))
                        pipeline["promote"] += int(packet.get("promotion", {}).get("status") == "promoted_to_active_memory")
                        external_calls += 1
                        outcomes.append({"department": plan.department_id, "kind": kind, "value": value, "packet": packet})
                else:
                    hits = self.store.cached_search(value, self.source_refresh_minutes)
                    if hits is None:
                        if external_calls >= self.max_external_calls:
                            outcomes.append({"department": plan.department_id, "kind": kind, "value": value, "skipped": "external_call_budget"})
                            continue
                        hits = self.web_searcher(value, self.max_search_results)
                        external_calls += 1
                        self.store.cache_search(value, hits)
                    if not hits:
                        raise RuntimeError("research search returned no sources")
                    scraped = 0
                    cached = 0
                    for hit in hits:
                        url = str(hit.get("url", "")).strip()
                        if not url:
                            continue
                        if self.store.source_is_fresh(url, self.source_refresh_minutes):
                            cached += 1
                            continue
                        if external_calls >= self.max_external_calls:
                            continue
                        try:
                            packet = self.store.ingest_source(self.web_fetcher(url), kind="web", manager=plan.manager, department=plan.department_id, query=value)
                            pipeline["fetch"] += 1
                            pipeline["reverse_engineer"] += int(bool(packet.get("reverse_engineering")))
                            pipeline["verify"] += int(packet.get("reverse_engineering", {}).get("status") == "verified_for_compaction")
                            pipeline["compact"] += int(bool(packet.get("summary")))
                            pipeline["promote"] += int(packet.get("promotion", {}).get("status") == "promoted_to_active_memory")
                            external_calls += 1
                            outcomes.append({"department": plan.department_id, "kind": "search", "value": value, "packet": packet})
                            scraped += 1
                        except Exception as error:
                            errors.append(f"{plan.department_id}: {url}: {error}")
                    if not scraped and not cached:
                        raise RuntimeError("research search sources could not be scraped")
            except Exception as error:
                errors.append(f"{plan.department_id}: {kind} {value}: {error}")
        completed = _iso()
        with self.store.lock:
            state = self._research_state()
            for plan in plans:
                department = state.setdefault("departments", {}).setdefault(plan.department_id, {})
                department.update({"last_run_at": completed, "last_status": "degraded" if errors else "ok", "last_error_count": len(errors), "cadence_minutes": plan.cadence_minutes, "manager": plan.manager})
                department["next_run_at"] = _iso(_now() + timedelta(minutes=plan.cadence_minutes))
            state.setdefault("cycles", []).append({"cycle_id": cycle_id, "completed_at": completed, "departments": [plan.department_id for plan in plans], "jobs": len(jobs), "packets": len(outcomes), "external_calls": external_calls, "pipeline": pipeline, "errors": errors[-20:]})
            state["cycles"] = state["cycles"][-100:]
            self.store._save()
        return {"cycle_id": cycle_id, "status": "degraded" if errors else "ok", "jobs": len(jobs), "packets": len(outcomes), "external_calls": external_calls, "pipeline": pipeline, "errors": errors, "completed_at": completed}

    def snapshot(self) -> dict[str, Any]:
        with self.store.lock:
            state = self._research_state()
            sources = list(self.store.data.get("sources", []))
            departments = []
            for plan in self.plans:
                owned = [item for item in sources if item.get("department") == plan.department_id]
                runtime = state.get("departments", {}).get(plan.department_id, {})
                departments.append({
                    "id": plan.department_id,
                    "name": plan.name,
                    "manager": plan.manager,
                    "enabled": plan.enabled,
                    "configured_topics": len(plan.topics),
                    "configured_queries": len(plan.queries),
                    "configured_urls": len(plan.urls),
                    "search_command": plan.search_command,
                    "capabilities": list(plan.capabilities),
                    "research_inputs": {
                        "topics": list(plan.topics),
                        "queries": list(plan.queries),
                        "urls": list(plan.urls),
                    },
                    "sources": len(owned),
                    "packets": len(owned),
                    "last_run_at": runtime.get("last_run_at"),
                    "next_run_at": runtime.get("next_run_at"),
                    "status": runtime.get("last_status", "WAITING"),
                    "last_error_count": runtime.get("last_error_count", 0),
                })
            return {"departments": departments, "research": {"due_departments": self.due_departments(), "cycles": list(state.get("cycles", []))[-10:]}}
