"""Core tests for smart_llm.py — model selection, inference, fallback, think-tag stripping."""

import smart_llm

# ---------------------------------------------------------------------------
# Helper: mock response class
# ---------------------------------------------------------------------------


class MockResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json


# ---------------------------------------------------------------------------
# Constants and TASK_TYPE_MAP
# ---------------------------------------------------------------------------


class TestConstants:
    """Test module-level constants."""

    def test_gateway_url_set(self):
        assert smart_llm.GATEWAY_URL is not None

    def test_model_url_set(self):
        assert smart_llm.MODEL_URL == "http://localhost:8021/v1/chat/completions"

    def test_fallback_model_id(self):
        assert (
            "Qwen3" in smart_llm.FALLBACK_MODEL_ID or "qwen" in smart_llm.FALLBACK_MODEL_ID.lower()
        )

    def test_task_type_map_has_analysis_keys(self):
        for key in ["resume_analysis", "skills_gap", "ats_diagnostic"]:
            assert key in smart_llm.TASK_TYPE_MAP
            assert smart_llm.TASK_TYPE_MAP[key] == "analysis"

    def test_task_type_map_has_reasoning_keys(self):
        for key in ["interview", "experience_chat", "campaign_planning"]:
            assert key in smart_llm.TASK_TYPE_MAP
            assert smart_llm.TASK_TYPE_MAP[key] == "reasoning"

    def test_task_type_map_has_coding_keys(self):
        for key in ["json_extraction", "technical_extraction", "resume_rewrite"]:
            assert key in smart_llm.TASK_TYPE_MAP
            assert smart_llm.TASK_TYPE_MAP[key] == "coding"

    def test_task_type_map_has_planning_keys(self):
        for key in ["career_planning", "campaign_strategy"]:
            assert key in smart_llm.TASK_TYPE_MAP
            assert smart_llm.TASK_TYPE_MAP[key] == "planning"


# ---------------------------------------------------------------------------
# _select_model
# ---------------------------------------------------------------------------


class TestSelectModel:
    """Tests for _select_model() — gateway model selection."""

    def test_success_returns_dict(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse(
                {
                    "model_id": "test-model",
                    "swap_id": "qwen3/coding",
                    "api_model_name": "test-model-api",
                    "endpoint_port": 8021,
                    "score": 95,
                    "task_type": "coding",
                }
            )

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm._select_model("test task", "coding")
        assert result is not None
        assert result["model_id"] == "test-model"
        assert result["swap_id"] == "qwen3/coding"

    def test_failure_returns_none(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse(None, status_code=500)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm._select_model("test task", "coding")
        assert result is None

    def test_exception_returns_none(self, monkeypatch):
        def mock_post(url, **kwargs):
            raise ConnectionError("Gateway down")

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm._select_model("test task", "coding")
        assert result is None

    def test_truncates_long_task(self, monkeypatch):
        captured = {}

        def mock_post(url, json=None, **kwargs):
            captured["json"] = json
            return MockResponse({"model_id": "m"}, 200)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        smart_llm._select_model("x" * 1000, "coding")
        assert len(captured["json"]["task"]) == 500


# ---------------------------------------------------------------------------
# _ensure_model_loaded
# ---------------------------------------------------------------------------


class TestEnsureModelLoaded:
    """Tests for _ensure_model_loaded() — swap management."""

    def test_empty_swap_id_returns_true(self, monkeypatch):
        result = smart_llm._ensure_model_loaded("")
        assert result is True

    def test_none_swap_id_returns_true(self, monkeypatch):
        result = smart_llm._ensure_model_loaded(None)
        assert result is True

    def test_cached_swap_id_returns_true(self, monkeypatch):
        smart_llm._current_swap_id = "test-swap"
        try:
            result = smart_llm._ensure_model_loaded("test-swap")
            assert result is True
        finally:
            smart_llm._current_swap_id = None

    def test_already_loaded_on_gateway(self, monkeypatch):
        smart_llm._current_swap_id = None

        def mock_get(url, **kwargs):
            return MockResponse({"current_swap_id": "target", "swap_in_progress": False})

        monkeypatch.setattr(smart_llm._http_client, "get", mock_get)
        monkeypatch.setattr(smart_llm._http_client, "post", lambda *a, **kw: MockResponse({}, 500))
        result = smart_llm._ensure_model_loaded("target")
        assert result is True
        smart_llm._current_swap_id = None


# ---------------------------------------------------------------------------
# call_direct
# ---------------------------------------------------------------------------


class TestCallDirect:
    """Tests for call_direct() — direct inference without model selection."""

    def test_returns_content(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse({"choices": [{"message": {"content": "Hello world"}}]}, 200)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm.call_direct("test prompt")
        assert result == "Hello world"

    def test_strips_think_tags(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse(
                {"choices": [{"message": {"content": "Before <think>reasoning</think> After"}}]},
                200,
            )

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm.call_direct("prompt")
        assert "<think>" not in result
        assert "Before" in result
        assert "After" in result

    def test_no_model_selection_called(self, monkeypatch):
        urls_called = []

        def mock_post(url, **kwargs):
            urls_called.append(url)
            return MockResponse({"choices": [{"message": {"content": "result"}}]}, 200)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        smart_llm.call_direct("prompt")
        assert not any("/api/models/select" in u for u in urls_called)

    def test_fallback_to_harness_on_failure(self, monkeypatch):
        call_count = {"n": 0}

        def mock_post(url, **kwargs):
            call_count["n"] += 1
            if "/v1/chat/completions" in url:
                return MockResponse(None, 500)
            if "/api/harness/run" in url:
                return MockResponse({"output": "harness fallback"}, 200)
            return MockResponse(None, 500)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm.call_direct("prompt")
        assert result == "harness fallback"


# ---------------------------------------------------------------------------
# call_harness
# ---------------------------------------------------------------------------


class TestCallHarness:
    """Tests for call_harness() — FTAL harness calls."""

    def test_returns_output(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse({"output": "harness response"}, 200)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm.call_harness("test task", task_type="coding")
        assert result == "harness response"

    def test_returns_result_field(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse({"result": "alt response"}, 200)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm.call_harness("test task")
        assert result == "alt response"

    def test_returns_none_on_failure(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse(None, 500)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm.call_harness("test task")
        assert result is None

    def test_returns_none_on_exception(self, monkeypatch):
        def mock_post(url, **kwargs):
            raise ConnectionError("No harness")

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        result = smart_llm.call_harness("test task")
        assert result is None

    def test_sends_correct_payload(self, monkeypatch):
        captured = {}

        def mock_post(url, json=None, **kwargs):
            captured["url"] = url
            captured["json"] = json
            return MockResponse({"output": "ok"}, 200)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        smart_llm.call_harness("my task", task_type="analysis", max_tokens=2048)
        assert captured["json"]["task"] == "my task"
        assert captured["json"]["task_type"] == "analysis"
        assert captured["json"]["max_tokens"] == 2048


# ---------------------------------------------------------------------------
# call_smart
# ---------------------------------------------------------------------------


class TestCallSmart:
    """Tests for call_smart() — full smart routing pipeline."""

    def test_resolves_task_type_from_map(self, monkeypatch):
        captured = {}

        def mock_post(url, json=None, **kwargs):
            if "/api/models/select" in url:
                captured["select_payload"] = json
                return MockResponse(
                    {
                        "model_id": "m",
                        "swap_id": "",
                        "api_model_name": "",
                        "endpoint_port": 8021,
                        "score": 90,
                        "task_type": "analysis",
                    },
                    200,
                )
            if "/v1/chat/completions" in url:
                return MockResponse({"choices": [{"message": {"content": "response"}}]}, 200)
            return MockResponse(None, 500)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        monkeypatch.setattr(smart_llm._http_client, "get", lambda *a, **kw: MockResponse({}, 500))
        result = smart_llm.call_smart("test", task_type="resume_analysis")
        assert result == "response"
        # Task type should be resolved to "analysis"
        assert captured["select_payload"]["task_type"] == "analysis"

    def test_uses_task_hint(self, monkeypatch):
        captured = {}

        def mock_post(url, json=None, **kwargs):
            if "/api/models/select" in url:
                captured["select_payload"] = json
                return MockResponse(None, 500)
            if "/v1/chat/completions" in url:
                return MockResponse({"choices": [{"message": {"content": "result"}}]}, 200)
            return MockResponse(None, 500)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        smart_llm.call_smart("long prompt...", task_hint="short hint")
        assert captured["select_payload"]["task"] == "short hint"

    def test_falls_back_when_selection_fails(self, monkeypatch):
        def mock_post(url, **kwargs):
            if "/api/models/select" in url:
                return MockResponse(None, 500)
            if "/v1/chat/completions" in url:
                return MockResponse({"choices": [{"message": {"content": "fallback ok"}}]}, 200)
            return MockResponse(None, 500)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        monkeypatch.setattr(smart_llm._http_client, "get", lambda *a, **kw: MockResponse({}, 500))
        result = smart_llm.call_smart("test")
        assert result == "fallback ok"

    def test_returns_none_when_all_fail(self, monkeypatch):
        def mock_post(url, **kwargs):
            return MockResponse(None, 500)

        monkeypatch.setattr(smart_llm._http_client, "post", mock_post)
        monkeypatch.setattr(smart_llm._http_client, "get", lambda *a, **kw: MockResponse({}, 500))
        result = smart_llm.call_smart("test")
        assert result is None


# ---------------------------------------------------------------------------
# get_current_model
# ---------------------------------------------------------------------------


class TestGetCurrentModel:
    """Tests for get_current_model() — swap status query."""

    def test_returns_gateway_response(self, monkeypatch):
        def mock_get(url, **kwargs):
            return MockResponse({"current_swap_id": "qwen3/coding", "swap_in_progress": False})

        monkeypatch.setattr(smart_llm._http_client, "get", mock_get)
        result = smart_llm.get_current_model()
        assert result["current_swap_id"] == "qwen3/coding"

    def test_returns_local_state_on_failure(self, monkeypatch):
        smart_llm._current_swap_id = "cached-swap"

        def mock_get(url, **kwargs):
            raise ConnectionError("Gateway down")

        monkeypatch.setattr(smart_llm._http_client, "get", mock_get)
        result = smart_llm.get_current_model()
        assert result["current_swap_id"] == "cached-swap"
        assert result["swap_in_progress"] is False
        smart_llm._current_swap_id = None
