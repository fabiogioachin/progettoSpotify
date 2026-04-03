"""Tests for wrapped_tasks.py — in-memory task store for Wrapped computation.

Covers:
- Task creation with correct structure and defaults
- Per-user limit enforcement (MAX_TASKS_PER_USER=3) with oldest eviction
- Ownership-based get_task (security)
- TTL-based cleanup of expired tasks
- Multiple tasks per user lifecycle
"""

import time

import pytest

from app.services.wrapped_tasks import (
    MAX_TASKS_PER_USER,
    TASK_TTL_SECONDS,
    _wrapped_tasks,
    create_task,
    find_completed_task,
    get_task,
    _cleanup_expired,
)


def _clear_tasks():
    """Reset the in-memory task store between tests."""
    _wrapped_tasks.clear()


class TestWrappedTaskStore:
    def setup_method(self):
        _clear_tasks()

    def test_create_task_returns_correct_structure(self):
        """create_task returns a dict with all expected fields and defaults."""
        task = create_task(user_id=1, time_range="medium_term")

        assert task["task_id"]  # non-empty UUID string
        assert task["user_id"] == 1
        assert task["time_range"] == "medium_term"
        assert task["status"] == "pending"
        assert task["phase"] == ""
        assert task["completed_services"] == 0
        assert task["total_services"] == 5
        assert task["waiting_seconds"] == 0
        assert task["error_detail"] is None
        assert task["created_at"] > 0
        assert task["results"] is not None
        assert task["results"]["temporal"] is None
        assert task["results"]["evolution"] is None
        assert task["results"]["profile"] is None
        assert task["results"]["top_tracks"] is None
        assert task["results"]["network"] is None

    def test_create_task_initial_available_slides(self):
        """New task starts with only ["intro"] in available_slides."""
        task = create_task(user_id=1, time_range="short_term")
        assert task["results"]["available_slides"] == ["intro"]

    def test_create_task_enforces_max_tasks_evicts_oldest(self):
        """When a user hits MAX_TASKS_PER_USER, the oldest task is evicted."""
        task_ids = []
        for i in range(MAX_TASKS_PER_USER):
            t = create_task(user_id=1, time_range="medium_term")
            # Stagger created_at so oldest is deterministic
            t["created_at"] = time.time() - (MAX_TASKS_PER_USER - i) * 10
            task_ids.append(t["task_id"])

        oldest_id = task_ids[0]

        # Creating one more should evict the oldest
        new_task = create_task(user_id=1, time_range="medium_term")
        assert new_task["task_id"] not in task_ids

        # Oldest should be gone
        assert get_task(oldest_id, user_id=1) is None

        # Newer ones should still exist
        for tid in task_ids[1:]:
            assert get_task(tid, user_id=1) is not None

    def test_get_task_returns_none_for_wrong_user(self):
        """get_task enforces ownership — another user cannot access the task."""
        task = create_task(user_id=1, time_range="medium_term")
        assert get_task(task["task_id"], user_id=2) is None

    def test_get_task_returns_none_for_nonexistent_task(self):
        """get_task returns None for a task_id that does not exist."""
        assert get_task("nonexistent-uuid", user_id=1) is None

    def test_get_task_returns_owned_task(self):
        """get_task returns the task for the correct owner."""
        task = create_task(user_id=1, time_range="long_term")
        retrieved = get_task(task["task_id"], user_id=1)
        assert retrieved is not None
        assert retrieved["task_id"] == task["task_id"]
        assert retrieved["time_range"] == "long_term"

    def test_cleanup_expired_removes_old_tasks(self):
        """_cleanup_expired removes tasks older than TASK_TTL_SECONDS."""
        task = create_task(user_id=1, time_range="medium_term")
        # Manually expire the task
        task["created_at"] = time.time() - TASK_TTL_SECONDS - 1

        _cleanup_expired()
        assert get_task(task["task_id"], user_id=1) is None

    def test_cleanup_keeps_recent_tasks(self):
        """_cleanup_expired does not remove tasks within TTL."""
        task = create_task(user_id=1, time_range="medium_term")
        _cleanup_expired()
        assert get_task(task["task_id"], user_id=1) is not None

    def test_multiple_creates_same_user(self):
        """Multiple tasks for the same user are independently tracked."""
        t1 = create_task(user_id=1, time_range="short_term")
        t2 = create_task(user_id=1, time_range="medium_term")
        t3 = create_task(user_id=1, time_range="long_term")

        assert t1["task_id"] != t2["task_id"] != t3["task_id"]
        assert get_task(t1["task_id"], user_id=1) is not None
        assert get_task(t2["task_id"], user_id=1) is not None
        assert get_task(t3["task_id"], user_id=1) is not None

    def test_different_users_independent(self):
        """Tasks from different users do not interfere with each other."""
        for _ in range(MAX_TASKS_PER_USER):
            create_task(user_id=1, time_range="medium_term")

        # User 2 should still create tasks freely
        task = create_task(user_id=2, time_range="short_term")
        assert task["user_id"] == 2
        assert get_task(task["task_id"], user_id=2) is not None

    def test_find_completed_task_returns_matching(self):
        """find_completed_task returns a completed task for matching user+time_range."""
        task = create_task(user_id=1, time_range="medium_term")
        task["status"] = "completed"
        found = find_completed_task(user_id=1, time_range="medium_term")
        assert found is not None
        assert found["task_id"] == task["task_id"]

    def test_find_completed_task_ignores_pending(self):
        """find_completed_task ignores tasks that are not completed."""
        create_task(user_id=1, time_range="medium_term")
        assert find_completed_task(user_id=1, time_range="medium_term") is None

    def test_find_completed_task_ignores_wrong_time_range(self):
        """find_completed_task only matches the requested time_range."""
        task = create_task(user_id=1, time_range="short_term")
        task["status"] = "completed"
        assert find_completed_task(user_id=1, time_range="medium_term") is None

    def test_find_completed_task_ignores_other_users(self):
        """find_completed_task enforces user ownership."""
        task = create_task(user_id=1, time_range="medium_term")
        task["status"] = "completed"
        assert find_completed_task(user_id=2, time_range="medium_term") is None

    def test_find_completed_task_ignores_expired(self):
        """find_completed_task does not return tasks past TTL."""
        task = create_task(user_id=1, time_range="medium_term")
        task["status"] = "completed"
        task["created_at"] = time.time() - TASK_TTL_SECONDS - 1
        assert find_completed_task(user_id=1, time_range="medium_term") is None
