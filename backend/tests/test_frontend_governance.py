"""Frontend governance tests — validates frontend build/test infrastructure exists and is properly structured.

Pure file inspection using pathlib and json. No subprocess calls.
Proves the DevOps/Frontend department is GOVERNED.
"""

import json
import re
from pathlib import Path

# Project root relative to this test file
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
TESTS_DIR = FRONTEND_DIR / "tests"
SRC_DIR = FRONTEND_DIR / "src"
COMPONENTS_DIR = SRC_DIR / "components"


class TestFrontendProjectStructure:
    """Verify frontend project structure and tooling."""

    def test_package_json_exists_and_valid(self):
        """package.json exists and parses as valid JSON."""
        pkg_path = FRONTEND_DIR / "package.json"
        assert pkg_path.exists(), "package.json missing"
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "name" in data or "dependencies" in data

    def test_react_18_in_dependencies(self):
        """React 18 is listed as a dependency."""
        pkg = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
        deps = pkg.get("dependencies", {})
        react_version = deps.get("react", "")
        assert react_version, "React not in dependencies"
        assert "18" in react_version, f"Expected React 18, got {react_version}"

    def test_vite_config_exists(self):
        """Vite build config present (vite.config.js or vite.config.ts)."""
        vite_js = FRONTEND_DIR / "vite.config.js"
        vite_ts = FRONTEND_DIR / "vite.config.ts"
        assert vite_js.exists() or vite_ts.exists(), "No vite config found"

    def test_build_script_defined(self):
        """package.json has a 'build' script."""
        pkg = json.loads((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"))
        scripts = pkg.get("scripts", {})
        assert "build" in scripts, "No build script in package.json"
        assert "vite" in scripts["build"].lower() or "react" in scripts["build"].lower()


class TestFrontendComponents:
    """Verify frontend components exist and are substantial."""

    def test_components_directory_has_files(self):
        """src/components/ has at least 10 component files."""
        assert COMPONENTS_DIR.exists(), "components/ directory missing"
        jsx_files = list(COMPONENTS_DIR.glob("*.jsx")) + list(COMPONENTS_DIR.glob("*.tsx"))
        assert len(jsx_files) >= 10, f"Only {len(jsx_files)} components found, need ≥10"

    def test_core_components_present(self):
        """Key application components exist."""
        expected = ["Dashboard", "Login", "ResumeUpload"]
        component_names = {f.stem for f in COMPONENTS_DIR.iterdir() if f.suffix in (".jsx", ".tsx")}
        for name in expected:
            assert name in component_names, f"Missing core component: {name}"

    def test_no_empty_components(self):
        """Component files have substantive content (>10 lines)."""
        jsx_files = list(COMPONENTS_DIR.glob("*.jsx")) + list(COMPONENTS_DIR.glob("*.tsx"))
        for f in jsx_files[:10]:  # Check first 10
            lines = f.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) > 10, f"{f.name} has only {len(lines)} lines"


class TestPlaywrightE2E:
    """Verify Playwright E2E test infrastructure."""

    def test_playwright_config_exists(self):
        """playwright.config.js is present."""
        config = FRONTEND_DIR / "playwright.config.js"
        assert config.exists(), "playwright.config.js missing"
        content = config.read_text(encoding="utf-8")
        assert "defineConfig" in content or "PlaywrightTestConfig" in content

    def test_spec_files_present(self):
        """At least 6 Playwright spec files exist."""
        spec_files = list(TESTS_DIR.glob("*.spec.js")) + list(TESTS_DIR.glob("*.spec.ts"))
        assert len(spec_files) >= 6, f"Only {len(spec_files)} spec files, need ≥6"

    def test_each_spec_has_test_calls(self):
        """Each spec file contains at least 1 test() call."""
        spec_files = list(TESTS_DIR.glob("*.spec.js")) + list(TESTS_DIR.glob("*.spec.ts"))
        for spec in spec_files:
            content = spec.read_text(encoding="utf-8")
            test_count = len(re.findall(r"\btest\s*\(", content))
            assert test_count >= 1, f"{spec.name} has 0 test() calls"

    def test_total_playwright_test_count(self):
        """Total Playwright tests across all specs is ≥30."""
        spec_files = list(TESTS_DIR.glob("*.spec.js")) + list(TESTS_DIR.glob("*.spec.ts"))
        total = 0
        for spec in spec_files:
            content = spec.read_text(encoding="utf-8")
            total += len(re.findall(r"\btest\s*\(", content))
        assert total >= 30, f"Only {total} total tests, need ≥30"

    def test_each_spec_has_expect_assertions(self):
        """Each spec file contains expect() assertions."""
        spec_files = list(TESTS_DIR.glob("*.spec.js")) + list(TESTS_DIR.glob("*.spec.ts"))
        for spec in spec_files:
            content = spec.read_text(encoding="utf-8")
            expect_count = len(re.findall(r"\bexpect\s*\(", content))
            assert expect_count >= 1, f"{spec.name} has 0 expect() assertions"

    def test_auth_spec_covers_login(self):
        """auth.spec.js tests login flow."""
        auth = TESTS_DIR / "auth.spec.js"
        assert auth.exists(), "auth.spec.js missing"
        content = auth.read_text(encoding="utf-8")
        assert "login" in content.lower() or "Login" in content

    def test_optimize_spec_covers_upload(self):
        """optimize.spec.js tests resume upload/optimization flow."""
        optimize = TESTS_DIR / "optimize.spec.js"
        assert optimize.exists(), "optimize.spec.js missing"
        content = optimize.read_text(encoding="utf-8")
        assert "upload" in content.lower() or "resume" in content.lower()

    def test_visual_spec_exists(self):
        """Visual regression spec exists."""
        visual = TESTS_DIR / "visual.spec.js"
        assert visual.exists(), "visual.spec.js missing"
        content = visual.read_text(encoding="utf-8")
        assert (
            "screenshot" in content.lower()
            or "visual" in content.lower()
            or "snapshot" in content.lower()
        )


class TestRepoHygiene:
    """Verify repository hygiene for frontend."""

    def test_node_modules_in_gitignore(self):
        """node_modules is in .gitignore."""
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore missing"
        content = gitignore.read_text(encoding="utf-8")
        assert "node_modules" in content, "node_modules not in .gitignore"

    def test_no_hardcoded_localhost_in_specs(self):
        """Spec files don't hardcode localhost URLs (should use baseURL config)."""
        spec_files = list(TESTS_DIR.glob("*.spec.js")) + list(TESTS_DIR.glob("*.spec.ts"))
        for spec in spec_files:
            content = spec.read_text(encoding="utf-8")
            # Allow localhost in comments but not in page.goto() calls
            goto_calls = re.findall(r"page\.goto\s*\(['\"]([^'\"]+)", content)
            for url in goto_calls:
                assert (
                    "localhost" not in url
                ), f"{spec.name} has hardcoded localhost in page.goto('{url}')"
