"""Background task manager. Runs long operations in threads so they
survive frontend disconnects. Frontend polls for status.

Task state is persisted to disk so restarts don't lose completed results."""

import threading
import traceback
import time
import json
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


TASK_STATE_FILE = Path(__file__).parent.parent.parent / "projects" / ".tasks.json"


@dataclass
class TaskStatus:
    task_id: str
    project: str
    operation: str
    status: str = "pending"       # pending, running, complete, error
    progress: int = 0             # 0-100
    message: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: float = 0
    finished_at: float = 0


_tasks: dict[str, TaskStatus] = {}
_lock = threading.Lock()
_counter = 0


def _save_state():
    """Persist completed/error task states to disk."""
    try:
        TASK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        persistable = {}
        for tid, t in _tasks.items():
            if t.status in ("complete", "error"):
                persistable[tid] = {
                    "task_id": t.task_id,
                    "project": t.project,
                    "operation": t.operation,
                    "status": t.status,
                    "progress": t.progress,
                    "message": t.message,
                    "result": t.result,
                    "error": t.error,
                    "started_at": t.started_at,
                    "finished_at": t.finished_at,
                }
        with open(TASK_STATE_FILE, "w") as f:
            json.dump(persistable, f, indent=2)
    except Exception:
        pass  # Non-critical — don't crash if state can't be saved


def _load_state():
    """Load persisted task states on startup."""
    global _counter
    if not TASK_STATE_FILE.exists():
        return
    try:
        with open(TASK_STATE_FILE) as f:
            data = json.load(f)
        for tid, d in data.items():
            _tasks[tid] = TaskStatus(**d)
        if _tasks:
            _counter = max(
                int(tid.rsplit("_", 1)[-1])
                for tid in _tasks.keys()
                if tid.rsplit("_", 1)[-1].isdigit()
            )
    except Exception:
        pass


# Load on import
_load_state()


def create_task(project: str, operation: str) -> str:
    global _counter
    with _lock:
        _counter += 1
        task_id = f"{operation}_{project}_{_counter}"
        _tasks[task_id] = TaskStatus(
            task_id=task_id,
            project=project,
            operation=operation,
            started_at=time.time(),
        )
    return task_id


def get_task(task_id: str) -> Optional[TaskStatus]:
    return _tasks.get(task_id)


def get_project_tasks(project: str) -> list[TaskStatus]:
    return [t for t in _tasks.values() if t.project == project]


def get_active_task(project: str, operation: str) -> Optional[TaskStatus]:
    """Get the most recent running/pending task for this project+operation."""
    candidates = [
        t for t in _tasks.values()
        if t.project == project and t.operation == operation
        and t.status in ("pending", "running")
    ]
    return candidates[-1] if candidates else None


def update_task(task_id: str, **kwargs):
    task = _tasks.get(task_id)
    if task:
        for k, v in kwargs.items():
            setattr(task, k, v)


def run_in_background(task_id: str, fn, *args, **kwargs):
    """Run fn in a background thread, updating task status."""
    def wrapper():
        task = _tasks.get(task_id)
        if not task:
            return
        task.status = "running"
        try:
            result = fn(task_id, *args, **kwargs)
            task.status = "complete"
            task.progress = 100
            task.result = result
            task.finished_at = time.time()
            _save_state()
        except Exception as e:
            traceback.print_exc()
            task.status = "error"
            task.error = str(e)
            task.finished_at = time.time()
            _save_state()

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()


def cleanup_old_tasks(max_age_hours: int = 24):
    """Remove completed/error tasks older than max_age_hours."""
    cutoff = time.time() - (max_age_hours * 3600)
    with _lock:
        to_remove = [
            tid for tid, t in _tasks.items()
            if t.status in ("complete", "error") and t.finished_at < cutoff
        ]
        for tid in to_remove:
            del _tasks[tid]
    if to_remove:
        _save_state()


def task_to_dict(task: TaskStatus) -> dict:
    return {
        "task_id": task.task_id,
        "project": task.project,
        "operation": task.operation,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "result": task.result,
        "error": task.error,
        "elapsed": round(
            (task.finished_at or time.time()) - task.started_at, 1
        ) if task.started_at else 0,
    }
