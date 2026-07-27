"""Single shared instances used by more than one tool module.

Exists to avoid two problems that come from each tool module creating its
own instance instead: (1) SeparatorClient's internal lock only serializes
GPU-bound separation calls made through the same instance — a second,
independently-created instance would let two separations race for GPU
memory at once, the same bug class fixed for ACEStepClient's cross-process
generate lock. (2) JobRegistry needs to be the same registry regardless of
which tool created a job, so check_vocal_track_status can poll a job
created by split_vocal_stems (or any future tool) and not just ones
created by generate_vocal_track.
"""
from songforge_mcp.job_registry import JobRegistry
from songforge_mcp.separator_client import SeparatorClient

jobs = JobRegistry()
separator_client = SeparatorClient()
