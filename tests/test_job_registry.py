from songforge_mcp.job_registry import JobRegistry


def test_list_all_returns_newest_first():
    registry = JobRegistry()
    job1 = registry.create()
    job1.created_at = 100.0
    job2 = registry.create()
    job2.created_at = 200.0

    result = registry.list_all()
    assert [j.id for j in result] == [job2.id, job1.id]


def test_list_all_returns_empty_for_fresh_registry():
    assert JobRegistry().list_all() == []


def test_list_all_reflects_eviction_of_old_finished_jobs():
    registry = JobRegistry(retention_seconds=0.0)
    job = registry.create()
    job.status = "complete"
    job.created_at = 0.0  # already older than a 0s retention window

    registry.create()  # triggers _evict_old_jobs as a side effect of create()

    assert job.id not in [j.id for j in registry.list_all()]
