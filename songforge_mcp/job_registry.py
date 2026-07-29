"""In-memory background job tracking for long-running generation.

Exists because of a real, measured failure: Claude Desktop cancelled a
generate_vocal_track call after exactly 240s with zero progress
notifications delivered in between (see docs/ARCHITECTURE.md for the
full story) — MCP's report_progress is a silent no-op unless the client
supplies a progressToken, which this client doesn't. Blocking one tool
call on the full cold-start-plus-generation duration is fundamentally
incompatible with that timeout. Jobs let generate_vocal_track return
immediately and hand back a job_id; the calling model polls a separate,
always-fast status tool instead.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    id: str
    status: str = "running"  # running | complete | error
    progress: float = 0.0
    message: str = "queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)


_RETENTION_SECONDS = 3600.0  # 1 hour - long enough that a slow, human-paced
# multi-step workflow (generate -> split -> transcribe) never loses a job
# it still needs; short enough that a long-running server (this one is
# meant to stay warm indefinitely) doesn't accumulate every job it has
# ever created for its entire lifetime, which the registry did before this.


class JobRegistry:
    def __init__(self, retention_seconds: float = _RETENTION_SECONDS) -> None:
        self._jobs: dict[str, Job] = {}
        self._retention_seconds = retention_seconds

    def create(self) -> Job:
        self._evict_old_jobs()
        job = Job(id=str(uuid.uuid4()))
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_all(self) -> list[Job]:
        """Newest first - matches the order a caller almost always wants
        ("what have I got running/just finished"), not insertion order."""
        return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def _evict_old_jobs(self) -> None:
        """Drops finished/errored jobs older than the retention window.
        Never evicts a "running" job regardless of age - only a completed
        or errored job is safe to forget, since a caller could still be
        about to poll a slow one."""
        cutoff = time.time() - self._retention_seconds
        stale_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status != "running" and job.created_at < cutoff
        ]
        for job_id in stale_ids:
            del self._jobs[job_id]
