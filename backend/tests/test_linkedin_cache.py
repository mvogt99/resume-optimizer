"""Test linkedin_cache.py — thread-safe per-user profile caching."""

import sys
import threading
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import linkedin_cache


class TestCacheOperations:
    def setup_method(self):
        """Clear in-memory cache before each test."""
        linkedin_cache._profiles.clear()

    def test_set_and_get_profile(self):
        profile = {"headline": "Engineer", "skills": ["Python"]}
        raw = {"headline": "Engineer", "skills": [{"name": "Python", "endorsements": 5}]}
        linkedin_cache.set_profile(99, profile, raw)
        result = linkedin_cache.get_profile(99)
        assert result is not None
        assert result["headline"] == "Engineer"

    def test_get_raw_returns_raw_data(self):
        profile = {"headline": "PM"}
        raw = {"headline": "PM", "skills": [{"name": "Agile", "endorsements": 10}]}
        linkedin_cache.set_profile(99, profile, raw)
        result = linkedin_cache.get_raw(99)
        assert result is not None
        assert result["skills"][0]["endorsements"] == 10

    def test_get_missing_returns_none(self):
        result = linkedin_cache.get_profile(999)
        assert result is None

    def test_get_raw_missing_returns_none(self):
        result = linkedin_cache.get_raw(999)
        assert result is None

    def test_has_profile_true_when_set(self):
        linkedin_cache.set_profile(88, {"x": 1}, {"x": 1})
        assert linkedin_cache.has_profile(88) is True

    def test_has_profile_false_when_missing(self):
        assert linkedin_cache.has_profile(777) is False

    def test_set_overwrites_existing(self):
        linkedin_cache.set_profile(99, {"v": 1}, {"v": 1})
        linkedin_cache.set_profile(99, {"v": 2}, {"v": 2})
        result = linkedin_cache.get_profile(99)
        assert result["v"] == 2

    def test_per_user_isolation(self):
        linkedin_cache.set_profile(1, {"user": "A"}, {"user": "A"})
        linkedin_cache.set_profile(2, {"user": "B"}, {"user": "B"})
        assert linkedin_cache.get_profile(1)["user"] == "A"
        assert linkedin_cache.get_profile(2)["user"] == "B"

    def test_string_user_id_converted_to_int(self):
        linkedin_cache.set_profile("42", {"x": 1}, {"x": 1})
        assert linkedin_cache.get_profile("42") is not None
        assert linkedin_cache.get_profile(42) is not None

    def test_thread_safe_access(self):
        """Concurrent writes don't cause data corruption."""
        errors = []

        def writer(uid):
            try:
                linkedin_cache.set_profile(uid, {"uid": uid}, {"uid": uid})
                result = linkedin_cache.get_profile(uid)
                if result is None or result["uid"] != uid:
                    errors.append(f"User {uid} got wrong data")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0, f"Thread errors: {errors}"
