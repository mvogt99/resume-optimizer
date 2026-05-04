"""QA Audit — single-file analysis: analyze_file() and _classify_tier().

Imported by qa_audit (main) to run per-file grading.
"""

import ast
from pathlib import Path

from qa_audit_classifier import TestFileAnalyzer, _check_mock_usage
from qa_audit_types import FileGrade, QUALITY_WEIGHTS


def analyze_file(filepath):
    """Analyze a single test file and return a FileGrade."""
    path = Path(filepath)
    source = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return FileGrade(
            path=str(path.name),
            tier="F",
            test_count=0,
            content_checks=0,
            db_queries=0,
            schema_checks=0,
            llm_verified=0,
            anti_patterns=["syntax_error"],
        )

    analyzer = TestFileAnalyzer()
    analyzer.visit(tree)

    # Check mock usage in source text
    mock_patterns = _check_mock_usage(source)
    all_anti_patterns = analyzer.anti_patterns + mock_patterns

    # Compute percentages
    total = analyzer.test_count or 1  # avoid div/0
    content_pct = (analyzer.content_checks / total) * 100
    db_pct = (analyzer.db_queries / total) * 100
    schema_pct = (analyzer.schema_checks / total) * 100

    # Detect if this is an API test (uses Flask test client) vs script/utility test
    is_api_test = False
    imports_requests = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            for arg in node.args.args:
                if arg.arg == "client":
                    is_api_test = True
                    break
        # Also check for get_json() calls (API response patterns)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_json"
        ):
            is_api_test = True
        # Check for `import requests` at module level
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "requests":
                    imports_requests = True
        if isinstance(node, ast.ImportFrom) and node.module == "requests":
            imports_requests = True
        if is_api_test:
            break

    # Files that import requests at module level are script/integration tests
    if imports_requests:
        is_api_test = False

    # Files that import governance tooling are tool tests, not API route tests
    imports_tool_module = False
    _tool_modules = {"schema_guard", "schema_helpers", "schemas"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _tool_modules:
            imports_tool_module = True
            break
    if imports_tool_module:
        is_api_test = False

    # Quality-weighted content: uses assertion quality weights instead of raw count
    quality_content_pct = (analyzer.content_quality_sum / total) * 100

    # Classify tier using quality-weighted content for honest grading
    tier = _classify_tier(
        quality_content_pct,
        db_pct,
        all_anti_patterns,
        is_api_test,
        test_count=analyzer.test_count,
        total_assertions=analyzer.total_assertions,
    )

    return FileGrade(
        path=str(path.name),
        tier=tier,
        test_count=analyzer.test_count,
        content_checks=analyzer.content_checks,
        db_queries=analyzer.db_queries,
        schema_checks=analyzer.schema_checks,
        llm_verified=analyzer.llm_verified,
        anti_patterns=all_anti_patterns,
        content_pct=round(content_pct, 1),
        db_pct=round(db_pct, 1),
        schema_pct=round(schema_pct, 1),
        quality_content_pct=round(quality_content_pct, 1),
        total_assertions=analyzer.total_assertions,
        file_name=str(path.name),
    )


def _classify_tier(
    content_pct, db_pct, anti_patterns, is_api_test=True, test_count=0, total_assertions=0
):
    """Classify a test file into a quality tier.

    Script/utility tests (is_api_test=False) are graded on assertion density:
    - A-tier: >=10 tests AND >=2.0 assertions per test (no anti-patterns)
    - B-tier: fewer tests or lower density (but no anti-patterns)

    API tests are graded on content/db percentages as before.
    """
    has_anti = len(anti_patterns) > 0
    if has_anti:
        return "F"
    if not is_api_test:
        assertion_density = total_assertions / max(test_count, 1)
        if test_count >= 10 and assertion_density >= 2.0:
            return "A"
        return "B"
    if content_pct > 70 and db_pct > 30:
        return "A"
    if content_pct > 50 and db_pct > 20:
        return "B"
    if content_pct > 30:
        return "C"
    if content_pct > 10:
        return "D"
    return "F"
