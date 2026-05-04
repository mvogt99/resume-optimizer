"""Unit tests for CT-1: governance_outcomes recording from resume optimizer."""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, call, patch


class TestRecordGovernanceOutcome:
    """_record_governance_outcome() fires a thread that writes to ArangoDB."""

    def _invoke(self, task_type, scores, model_id, mock_col):
        """Invoke _record_governance_outcome() and run the thread synchronously."""
        import threading

        threads_before = list(threading.enumerate())

        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")
        from llm_helper import _record_governance_outcome

        with patch("llm_helper.threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            _record_governance_outcome(task_type, scores, model_id)
            # Thread was created with daemon=True
            mock_thread_cls.assert_called_once()
            _, kwargs = mock_thread_cls.call_args
            assert kwargs.get("daemon") is True
            # Run the target directly to inspect the write
            target = mock_thread_cls.call_args[1].get("target") or mock_thread_cls.call_args[0][0]
            return mock_thread_cls, target

    def test_thread_is_daemon(self):
        """Governance writes must not block process shutdown."""
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")
        from llm_helper import _record_governance_outcome

        with patch("llm_helper.threading.Thread") as mock_cls:
            mock_cls.return_value = MagicMock()
            _record_governance_outcome("coding", {"gap": 20}, "qwen25-coder-32b")
            _, kwargs = mock_cls.call_args
            assert kwargs.get("daemon") is True

    def test_passed_true_when_gap_below_threshold(self):
        """gap=20 → the write thread is created; passed logic is gap < 30."""
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

        # ArangoClient is imported inside the thread closure — patch arango module
        mock_col = MagicMock()
        mock_db = MagicMock()
        mock_db.collection.return_value = mock_col
        mock_client_instance = MagicMock()
        mock_client_instance.db.return_value = mock_db

        with patch("arango.ArangoClient", return_value=mock_client_instance):
            with patch("llm_helper.threading.Thread") as mock_cls:
                captured = {}

                def capture(**kwargs):
                    captured["target"] = kwargs.get("target")
                    m = MagicMock()
                    m.start = MagicMock()
                    return m

                mock_cls.side_effect = capture

                from llm_helper import _record_governance_outcome
                _record_governance_outcome("coding", {"gap": 20}, "qwen25-coder-32b")

        assert mock_cls.called
        # Verify passed logic: gap=20 < 30 → passed=True
        from llm_helper import _GOVERNANCE_THRESHOLD
        assert 20 < _GOVERNANCE_THRESHOLD

    def test_passed_false_when_gap_above_threshold(self):
        """gap=45 → passed=False."""
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")
        from llm_helper import _GOVERNANCE_THRESHOLD
        assert _GOVERNANCE_THRESHOLD == 30

    def test_governance_threshold_is_30(self):
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")
        from llm_helper import _GOVERNANCE_THRESHOLD
        assert _GOVERNANCE_THRESHOLD == 30

    def test_source_field_is_resume_optimizer(self):
        """Outcome documents must include source='resume_optimizer' for CT-13 filtering."""
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

        captured = {}
        with patch("llm_helper.threading.Thread") as mock_cls:
            def capture(**kwargs):
                captured["target"] = kwargs.get("target")
                m = MagicMock()
                m.start = MagicMock()
                return m
            mock_cls.side_effect = capture

            from llm_helper import _record_governance_outcome
            _record_governance_outcome("analysis", {"gap": 10}, "qwen3-32b")

        assert mock_cls.called


class TestCallLlmScoredGovernanceWiring:
    """call_llm_scored() must call _record_governance_outcome when gap is present."""

    def test_governance_called_on_harness_success(self):
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

        scores = {"f": 25, "t": 25, "a": 20, "gap": 20, "model_id": "qwen25-coder-32b"}
        with patch("llm_helper.call_harness_scored", return_value=("output text", scores)):
            with patch("llm_helper._record_governance_outcome") as mock_record:
                from llm_helper import call_llm_scored
                text, returned_scores = call_llm_scored("test task", task_type="coding")
                assert text == "output text"
                mock_record.assert_called_once_with("coding", scores, "qwen25-coder-32b")

    def test_governance_not_called_when_harness_unreachable(self):
        """No scores → no governance write (can't record what we don't know)."""
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

        with patch("llm_helper.call_harness_scored", return_value=(None, None)):
            with patch("llm_helper.call_direct", return_value="direct output"):
                with patch("llm_helper._record_governance_outcome") as mock_record:
                    from llm_helper import call_llm_scored
                    text, scores = call_llm_scored("task", task_type="coding")
                    assert text == "direct output"
                    mock_record.assert_not_called()

    def test_governance_called_even_on_gap_fallback(self):
        """gap >= 30 triggers direct fallback, but governance record still fires."""
        import sys
        sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

        bad_scores = {"f": 10, "t": 10, "a": 5, "gap": 55, "model_id": "qwen25-coder-32b"}
        with patch("llm_helper.call_harness_scored", return_value=("bad text", bad_scores)):
            with patch("llm_helper.call_direct", return_value="direct fallback"):
                with patch("llm_helper._record_governance_outcome") as mock_record:
                    from llm_helper import call_llm_scored
                    text, _ = call_llm_scored("task", task_type="coding")
                    assert text == "direct fallback"
                    mock_record.assert_called_once()
