"""QA Audit — assertion quality classifier and AST analysis.

Contains TestFileAnalyzer (ast.NodeVisitor), assertion quality classification
helpers, and mock-usage detection.  Imported by qa_audit_analyzer.
"""

import ast

from qa_audit_types import QUALITY_WEIGHTS


# ---------------------------------------------------------------------------
# Assertion Quality Classifier
# ---------------------------------------------------------------------------


def classify_assertion_quality(assert_node, json_vars=None):
    """Classify an assertion's quality level via AST inspection.

    Returns "trivial", "structural", or "semantic".

    trivial (0.5):   isinstance checks, is/is not None, status_code-only,
                     always-true len>=0
    structural (0.75): key-in-dict presence, non-trivial len checks (>0, ==N)
    semantic (1.0):   field value equality/comparison, subscript comparisons,
                     substring checks on field values
    """
    if json_vars is None:
        json_vars = set()
    test = assert_node.test

    # --- Compare nodes (the most common assertion pattern) ---
    if isinstance(test, ast.Compare):
        return _classify_compare(test, json_vars)

    # --- isinstance(...) as bare call in assert ---
    if isinstance(test, ast.Call):
        if isinstance(test.func, ast.Name) and test.func.id == "isinstance":
            return "trivial"
        # hasattr(...) → trivial
        if isinstance(test.func, ast.Name) and test.func.id == "hasattr":
            return "trivial"

    # --- UnaryOp: assert not X ---
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return "structural"

    # --- BoolOp: assert A or B, assert A and B ---
    if isinstance(test, ast.BoolOp):
        # Best quality among sub-expressions
        best = "trivial"
        for val in test.values:
            if isinstance(val, ast.Compare):
                q = _classify_compare(val, json_vars)
            elif isinstance(val, ast.Call):
                if isinstance(val.func, ast.Name) and val.func.id == "isinstance":
                    q = "trivial"
                else:
                    q = "structural"
            else:
                q = "structural"
            if QUALITY_WEIGHTS.get(q, 0) > QUALITY_WEIGHTS.get(best, 0):
                best = q
        return best

    # Default: if we can't classify, be conservative
    return "structural"


def _classify_compare(cmp_node, json_vars):
    """Classify an ast.Compare node."""
    left = cmp_node.left
    ops = cmp_node.ops
    comparators = cmp_node.comparators

    if not ops or not comparators:
        return "structural"

    op = ops[0]
    right = comparators[0]

    # --- isinstance() as left side of Compare (rare but possible) ---
    if isinstance(left, ast.Call) and isinstance(left.func, ast.Name):
        if left.func.id == "isinstance":
            return "trivial"

    # --- is / is not None → trivial ---
    if isinstance(op, (ast.Is, ast.IsNot)):
        if isinstance(right, ast.Constant) and right.value is None:
            return "trivial"
        return "structural"

    # --- status_code checks → trivial (not content) ---
    if _is_status_code_ref(left):
        return "trivial"

    # --- len() comparisons ---
    if isinstance(left, ast.Call) and isinstance(left.func, ast.Name):
        if left.func.id == "len":
            # len(x) >= 0 → trivial (always true)
            if isinstance(op, ast.GtE) and isinstance(right, ast.Constant) and right.value == 0:
                return "trivial"
            # len(x) > 0, len(x) == N, len(x) >= N → structural
            return "structural"

    # --- "in" operator ---
    if isinstance(op, ast.In):
        # "key" in data → structural (key presence)
        if isinstance(left, ast.Constant) and isinstance(right, ast.Name):
            return "structural"
        # "key" in data[...] or "text" in data.get(...) → semantic (value check)
        if isinstance(left, ast.Constant) and isinstance(right, (ast.Subscript, ast.Call)):
            return "semantic"
        # var in (set/tuple) where var is status_code → trivial
        if _is_status_code_ref(left):
            return "trivial"
        return "structural"

    if isinstance(op, ast.NotIn):
        if isinstance(right, (ast.Subscript, ast.Call)):
            return "semantic"
        return "structural"

    # --- Subscript or Attribute comparisons → semantic ---
    # data["key"] == value, data.get("key") == value, rows[0]["status"] == "x"
    if isinstance(left, ast.Subscript):
        return "semantic"
    if isinstance(left, ast.Call) and isinstance(left.func, ast.Attribute):
        if left.func.attr == "get":
            return "semantic"

    # --- Right side is subscript (value == data["key"]) → semantic ---
    if isinstance(right, ast.Subscript):
        return "semantic"

    # --- Name-to-Constant comparisons involving json_vars → semantic ---
    if isinstance(left, ast.Name) and left.id in json_vars:
        if isinstance(right, ast.Constant):
            return "semantic"
        return "structural"

    # --- Numeric comparisons with json-derived variables ---
    if isinstance(left, ast.Name) and isinstance(right, ast.Constant):
        if isinstance(right.value, (int, float)):
            return "semantic"

    # Fallback
    return "structural"


def _is_status_code_ref(node):
    """Check if an AST node references .status_code."""
    if isinstance(node, ast.Attribute) and node.attr == "status_code":
        return True
    return False


# ---------------------------------------------------------------------------
# AST Analysis
# ---------------------------------------------------------------------------


class TestFileAnalyzer(ast.NodeVisitor):
    """Walk a test file AST and classify assertions.

    A test is "content-checked" if it calls get_json() AND makes assertions
    on the resulting data (checking field values, keys, types, etc.).
    """

    def __init__(self):
        self.test_count = 0
        self.content_checks = 0
        self.content_quality_sum = 0.0  # sum of quality weights per content-checked test
        self.db_queries = 0
        self.schema_checks = 0
        self.llm_verified = 0
        self.total_assertions = 0
        self.anti_patterns = []
        self._current_function = None

    def visit_FunctionDef(self, node):
        if node.name.startswith("test_"):
            self.test_count += 1
            self._current_function = node.name

            # Analyze function body holistically
            has_content, has_db, has_schema, has_llm, quality, assertion_count = (
                self._analyze_function(node)
            )

            self.total_assertions += assertion_count
            if has_content:
                self.content_checks += 1
                self.content_quality_sum += quality
            if has_db:
                self.db_queries += 1
            if has_schema:
                self.schema_checks += 1
            if has_llm:
                self.llm_verified += 1

            # Check anti-patterns
            self._check_anti_patterns(node)

            self._current_function = None
        else:
            self.generic_visit(node)

    def _analyze_function(self, func_node):
        """Analyze a test function for content checks, DB queries, etc."""
        src = ast.dump(func_node)

        # Content check: function calls get_json() and has assertions beyond status_code
        has_get_json = "get_json" in src
        has_json_call = "json()" in src

        # Track variable names that hold JSON data
        json_vars = set()
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assign):
                assign_src = ast.dump(node.value)
                if "get_json" in assign_src:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            json_vars.add(target.id)

        # Count assertions that check JSON content (not just status_code)
        # Also classify quality of each content assertion
        content_assertions = 0
        best_quality = "trivial"
        total_assertions = 0
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                total_assertions += 1
                assert_src = ast.dump(node.test)

                is_content = False
                # Direct get_json checks
                if "get_json" in assert_src:
                    is_content = True
                else:
                    # Assertions on json_var["key"], json_var.get("key"), etc.
                    for var in json_vars:
                        if var in assert_src:
                            is_content = True
                            break
                    else:
                        # Check for common variable patterns
                        if any(
                            v in assert_src
                            for v in (
                                "data[",
                                "data.",
                                "result[",
                                "result.",
                                "body[",
                                "body.",
                                "resp_data",
                                "response_data",
                                "json_data",
                                "'in' data",
                                "in data",
                            )
                        ):
                            is_content = True

                if is_content:
                    content_assertions += 1
                    q = classify_assertion_quality(node, json_vars)
                    if QUALITY_WEIGHTS.get(q, 0) > QUALITY_WEIGHTS.get(best_quality, 0):
                        best_quality = q

        has_content = (has_get_json or has_json_call) and content_assertions > 0
        # Quality weight for this test: best assertion quality found
        quality_weight = QUALITY_WEIGHTS.get(best_quality, 0.5) if has_content else 0.0

        # DB query check
        has_db = "query_db" in src or "_query_db" in src

        # Schema check
        has_schema = "assert_schema" in src or "validate_schema" in src

        # LLM verified
        has_llm = False
        for arg in func_node.args.args:
            if arg.arg == "require_harness":
                has_llm = True

        return has_content, has_db, has_schema, has_llm, quality_weight, total_assertions

    def _check_anti_patterns(self, func_node):
        """Detect anti-patterns in a test function."""
        # always_true: assert True, assert len(x) >= 0
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                assert_src = ast.dump(node.test)
                if assert_src == "Constant(value=True)":
                    self._add_anti_pattern("always_true", self._current_function)
                # assert len(x) >= 0  (always true — len() is never negative)
                if isinstance(node.test, ast.Compare):
                    cmp = node.test
                    left_src = ast.dump(cmp.left)
                    if (
                        "len" in left_src
                        and len(cmp.ops) == 1
                        and isinstance(cmp.ops[0], ast.GtE)
                        and len(cmp.comparators) == 1
                        and isinstance(cmp.comparators[0], ast.Constant)
                        and cmp.comparators[0].value == 0
                    ):
                        self._add_anti_pattern("always_true", self._current_function)

        # silent_pass: if resp.status_code == 200: assert ... (with no else)
        for node in ast.walk(func_node):
            if isinstance(node, ast.If) and not node.orelse:
                if_src = ast.dump(node.test)
                if "status_code" in if_src and "Eq()" in if_src and "Constant(value=200)" in if_src:
                    body_asserts = sum(1 for c in ast.walk(node) if isinstance(c, ast.Assert))
                    if body_asserts > 0:
                        has_prior_status_assert = False
                        for sibling in ast.iter_child_nodes(func_node):
                            if sibling is node:
                                break
                            if isinstance(sibling, ast.Assert):
                                sib_src = ast.dump(sibling.test)
                                if "status_code" in sib_src:
                                    has_prior_status_assert = True
                        if not has_prior_status_assert:
                            self._add_anti_pattern("silent_pass", self._current_function)

        # broad_500: assert status_code in (...) where tuple contains 500
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                assert_src = ast.dump(node.test)
                if "status_code" in assert_src and "In()" in assert_src and "500" in assert_src:
                    self._add_anti_pattern("broad_500", self._current_function)

    def _add_anti_pattern(self, pattern_type, func_name):
        """Add an anti-pattern if not already recorded."""
        entry = f"{pattern_type}:{func_name}"
        if entry not in self.anti_patterns:
            self.anti_patterns.append(entry)


def _check_mock_usage(source_text):
    """Check for mock/patch usage via AST (ignores string literals)."""
    patterns = []
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return patterns

    for node in ast.walk(tree):
        # Check decorators: @mock.patch, @patch
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                dec_src = ast.dump(dec)
                if (
                    ("mock" in dec_src.lower() and "patch" in dec_src.lower())
                    or (isinstance(dec, ast.Attribute) and dec.attr == "patch")
                    or (isinstance(dec, ast.Name) and dec.id == "patch")
                ):
                    patterns.append(f"mock_usage:decorator_{node.name}")

        # Check calls: MagicMock(), Mock()
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("MagicMock", "Mock"):
                patterns.append("mock_usage:instantiation")
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("MagicMock", "Mock"):
                patterns.append("mock_usage:instantiation")

        # Check imports: from unittest.mock import ...
        if isinstance(node, ast.ImportFrom) and node.module and "mock" in node.module:
            patterns.append("mock_usage:import")

    return list(set(patterns))  # deduplicate
