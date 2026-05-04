"""Smoke tests: verify split modules import without errors."""

import importlib
import sys

SPLIT_MODULES = [
    ("project_analyzer", "ProjectAnalyzer"),
    ("project_analyzer_extraction", "classify_documents"),
    ("project_analyzer_synthesis", "analyze_documents"),
    ("project_analyzer_arango", "write_to_arango"),
    ("experience_chat", "ExperienceExtractor"),
    ("experience_chat_stages", "build_extraction_prompt"),
    ("experience_chat_db", "save_message"),
    ("deep_profile", "DeepProfileEngine"),
    ("deep_profile_sources", "get_project_data"),
    ("deep_profile_synthesis", "synthesize_profile"),
    ("builder_interview", "BuilderInterviewer"),
    ("builder_interview_stages", "call_llm_followup"),
    ("deep_interview", "DeepInterviewer"),
    ("deep_interview_handlers", "build_interview_prompt"),
]


class TestModuleImports:
    """Each split module imports without error and exports expected names."""

    def test_all_modules_import(self):
        failures = []
        for mod_name, _ in SPLIT_MODULES:
            try:
                importlib.import_module(mod_name)
            except Exception as e:
                failures.append(f"{mod_name}: {e}")
        assert not failures, "Import failures:\n" + "\n".join(failures)

    def test_all_modules_export_expected_names(self):
        missing = []
        for mod_name, expected_attr in SPLIT_MODULES:
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, expected_attr):
                missing.append(f"{mod_name} missing '{expected_attr}'")
        assert not missing, "Missing exports:\n" + "\n".join(missing)

    def test_parent_modules_delegate_correctly(self):
        """Parent modules still expose their main class/singleton."""
        pa = importlib.import_module("project_analyzer")
        assert hasattr(pa, "ProjectAnalyzer")
        assert hasattr(pa, "get_project_analyzer")

        ec = importlib.import_module("experience_chat")
        assert hasattr(ec, "ExperienceExtractor")

        dp = importlib.import_module("deep_profile")
        assert hasattr(dp, "DeepProfileEngine")

        bi = importlib.import_module("builder_interview")
        assert hasattr(bi, "BuilderInterviewer")

        di = importlib.import_module("deep_interview")
        assert hasattr(di, "DeepInterviewer")

    def test_no_circular_imports(self):
        """Import all split modules in sequence — catches circulars."""
        for mod_name, _ in SPLIT_MODULES:
            if mod_name in sys.modules:
                del sys.modules[mod_name]

        for mod_name, _ in SPLIT_MODULES:
            importlib.import_module(mod_name)
