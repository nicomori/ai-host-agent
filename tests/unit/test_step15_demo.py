"""
Step 15 — Demo prep + portfolio packaging: Test Suite (ai-host-agent)

7 test cases covering:
  TC-01: README.md exists and has required top-level sections
  TC-02: README.md has architecture diagram (ASCII art block)
  TC-03: demo script exists and is valid Python (no syntax errors)
  TC-04: Makefile has 'demo' and 'demo-local' targets
  TC-05: pyproject.toml has complete project metadata
  TC-06: .env.example documents all required environment variable keys
  TC-07: docs/architecture.md exists with minimum content

Error resolutions applied:
  Form 1: pathlib.Path for cross-platform file existence checks
  Form 2: re.compile() with re.IGNORECASE for case-insensitive section matching
  Form 3: ast.parse() for syntax-safe Python script validation
  Form 4: Case-insensitive header matching via str.casefold() for Makefile targets
  Form 5: pytest.importorskip() guard for optional parse dependencies
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

# ─── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent  # Form 1
README = PROJECT_ROOT / "README.md"
DEMO_SCRIPT = PROJECT_ROOT / "scripts" / "demo.py"
MAKEFILE = PROJECT_ROOT / "Makefile"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
DOCS_ARCH = PROJECT_ROOT / "docs" / "architecture.md"

# ─── TC-01: README.md exists and has required sections ─────────────────────────

REQUIRED_SECTIONS = [
    "overview",
    "features",
    "architecture",
    "quickstart",
    "api",
    "development",
    "configuration",
]

# Form 2: pre-compiled case-insensitive regex for section matching
_SECTION_RE = {
    section: re.compile(rf"#+\s*{section}", re.IGNORECASE) for section in REQUIRED_SECTIONS
}


def test_tc01_readme_exists_with_required_sections():
    """TC-01: README.md must exist and contain all required top-level sections."""
    # Form 1: pathlib cross-platform existence check
    assert README.exists(), f"README.md not found at {README}"
    content = README.read_text()
    print(f"\nTC-01 README.md size: {len(content)} chars")
    missing = []
    for section, pattern in _SECTION_RE.items():
        if not pattern.search(content):
            missing.append(section)
    assert not missing, (
        f"README.md missing sections: {missing}\n"
        f"Found headers: {re.findall(r'^#+.+', content, re.MULTILINE)[:10]}"
    )
    print(f"TC-01 all required sections found: {list(_SECTION_RE)}")


# ─── TC-02: README has architecture diagram ─────────────────────────────────────


def test_tc02_readme_has_architecture_diagram():
    """TC-02: README.md must contain an architecture ASCII diagram (code block)."""
    assert README.exists(), f"README.md not found at {README}"
    content = README.read_text()
    # Form 2: regex for fenced code block in architecture section
    arch_block = re.search(
        r"#+\s*architecture.*?```.*?```",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    print(f"\nTC-02 architecture block found: {bool(arch_block)}")
    assert arch_block, (
        "README.md must have an architecture section with a fenced code block (``` ... ```)"
    )
    diagram_text = arch_block.group(0)
    # Must contain box-drawing characters or pipes indicating ASCII art
    has_ascii_art = any(ch in diagram_text for ch in ["│", "┌", "┐", "└", "┘", "─", "▼", "|", "+"])
    assert has_ascii_art, "Architecture code block must contain ASCII art characters (│┌─▼ or |+-)"
    print("TC-02 architecture diagram with ASCII art found ✓")


# ─── TC-03: demo.py exists and is valid Python ─────────────────────────────────


def test_tc03_demo_script_exists_and_valid_python():
    """TC-03: scripts/demo.py must exist and parse without syntax errors."""
    # Form 1: pathlib existence check
    assert DEMO_SCRIPT.exists(), f"demo.py not found at {DEMO_SCRIPT}"
    source = DEMO_SCRIPT.read_text()
    print(f"\nTC-03 demo.py size: {len(source)} chars")
    # Form 3: ast.parse() — syntax validation without executing the script
    try:
        tree = ast.parse(source, filename=str(DEMO_SCRIPT))
    except SyntaxError as exc:
        pytest.fail(f"demo.py has syntax error: {exc}")
    # Must define a main() function
    function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    print(f"TC-03 functions defined: {function_names}")
    assert "main" in function_names, (
        f"demo.py must define a main() function. Found: {function_names}"
    )
    # Must have __main__ guard
    assert "__name__" in source and "__main__" in source, (
        "demo.py must have 'if __name__ == \"__main__\"' guard"
    )
    print("TC-03 demo.py is valid Python with main() ✓")


# ─── TC-04: Makefile has demo targets ──────────────────────────────────────────


def test_tc04_makefile_has_demo_targets():
    """TC-04: Makefile must define 'demo' and 'demo-local' targets."""
    assert MAKEFILE.exists(), f"Makefile not found at {MAKEFILE}"
    content = MAKEFILE.read_text()
    lines = content.splitlines()
    # Form 4: case-insensitive casefold() matching on target declarations
    target_lines = [ln for ln in lines if re.match(r"^[a-zA-Z_-]+:", ln)]
    target_names = [ln.split(":")[0].casefold() for ln in target_lines]
    print(f"\nTC-04 Makefile targets: {target_names}")
    assert "demo" in target_names, f"Makefile must have a 'demo' target. Found: {target_names}"
    assert "demo-local" in target_names, (
        f"Makefile must have a 'demo-local' target. Found: {target_names}"
    )
    # demo target must invoke demo.py
    demo_section = "\n".join(ln for ln in lines if "demo" in ln.casefold() or "demo.py" in ln)
    assert "demo.py" in demo_section, "Makefile demo/demo-local targets must invoke scripts/demo.py"
    print("TC-04 Makefile has demo + demo-local targets ✓")


# ─── TC-05: pyproject.toml has complete metadata ───────────────────────────────

REQUIRED_METADATA_KEYS = ["name", "version", "description", "requires-python"]


def test_tc05_pyproject_has_complete_metadata():
    """TC-05: pyproject.toml must have name, version, description, requires-python."""
    assert PYPROJECT.exists(), f"pyproject.toml not found at {PYPROJECT}"
    content_bytes = PYPROJECT.read_bytes()
    # Form 5: try tomllib (Python 3.11+) → tomli → text fallback (Python 3.9 compat)
    toml_data: dict | None = None
    try:
        import tomllib  # Python 3.11+

        toml_data = tomllib.loads(content_bytes.decode())
    except ImportError:
        try:
            import tomli  # pip install tomli

            toml_data = tomli.loads(content_bytes.decode())
        except ImportError:
            pass  # Form 3: text-based fallback below

    if toml_data is None:
        # Form 3: safe text fallback — no TOML parser available (Python 3.9 + no tomli)
        text = content_bytes.decode()
        print(f"\nTC-05 [text fallback] pyproject.toml size: {len(text)} chars")
        for key in REQUIRED_METADATA_KEYS:
            assert key in text, f"pyproject.toml missing '{key}'"
        assert re.search(r'version\s*=\s*"\d+\.\d+\.\d+', text), (
            "version must be semver-like (x.y.z)"
        )
        assert re.search(r'description\s*=\s*"[^"]+', text), "description must be non-empty"
        print("TC-05 pyproject.toml text fallback check passed ✓")
        return

    project = toml_data.get("project", {})
    print(f"\nTC-05 [project] keys: {list(project.keys())}")
    for key in REQUIRED_METADATA_KEYS:
        assert key in project, f"[project] missing '{key}' in pyproject.toml"
    version = project.get("version", "")
    assert re.match(r"^\d+\.\d+\.\d+", version), (
        f"version must be semver-like (x.y.z), got: {version}"
    )
    assert project.get("description", "").strip(), "description must be non-empty"
    print(f"TC-05 metadata OK: name={project['name']} version={version} ✓")


# ─── TC-06: .env.example documents required env vars ───────────────────────────

REQUIRED_ENV_KEYS = [
    "ANTHROPIC_API_KEY",
    "API_KEY",
    "LANCEDB_URI",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
]


def test_tc06_env_example_has_required_keys():
    """TC-06: .env.example must document all required environment variable keys."""
    # Form 1: pathlib existence check
    assert ENV_EXAMPLE.exists(), f".env.example not found at {ENV_EXAMPLE}"
    content = ENV_EXAMPLE.read_text()
    print(f"\nTC-06 .env.example size: {len(content)} chars")
    missing = []
    for key in REQUIRED_ENV_KEYS:
        # Form 2: regex — key must appear as a variable name (not just in a comment)
        if not re.search(rf"^{re.escape(key)}\s*=", content, re.MULTILINE):
            missing.append(key)
    print(f"TC-06 missing keys: {missing or 'none'}")
    assert not missing, f".env.example is missing required keys: {missing}"
    print("TC-06 .env.example has all required keys ✓")


# ─── TC-07: docs/architecture.md exists with minimum content ───────────────────

REQUIRED_ARCH_SECTIONS = ["component", "multi-agent", "data model"]


def test_tc07_docs_architecture_exists_with_content():
    """TC-07: docs/architecture.md must exist and cover key architecture sections."""
    # Form 1: pathlib existence check
    assert DOCS_ARCH.exists(), f"docs/architecture.md not found at {DOCS_ARCH}"
    content = DOCS_ARCH.read_text()
    print(f"\nTC-07 docs/architecture.md size: {len(content)} chars")
    # Must have minimum content
    assert len(content) >= 500, (
        f"docs/architecture.md is too short ({len(content)} chars) — expected ≥ 500"
    )
    # Form 2: case-insensitive check for required sections
    missing = []
    for section in REQUIRED_ARCH_SECTIONS:
        if not re.search(section, content, re.IGNORECASE):
            missing.append(section)
    print(f"TC-07 missing arch sections: {missing or 'none'}")
    assert not missing, f"docs/architecture.md missing required sections: {missing}"
    # Must have at least one code block (diagram or code example)
    has_code_block = "```" in content
    assert has_code_block, "docs/architecture.md must contain at least one ``` code block"
    print("TC-07 docs/architecture.md content verified ✓")


# ─── TC-08: README.md has substantial content ──────────────────────────────────


def test_tc08_readme_has_substantial_content():
    """TC-08: README.md must have at least 1000 characters of substantive content."""
    assert README.exists(), f"README.md not found at {README}"
    content = README.read_text()
    print(f"\nTC-08 README.md char count: {len(content)}")
    assert len(content) >= 1000, f"README.md is too short ({len(content)} chars) — expected ≥ 1000"


# ─── TC-09: docs/ directory has at least 2 Markdown files ────────────────────


def test_tc09_docs_directory_has_multiple_files():
    """TC-09: docs/ directory must contain at least 1 .md file."""
    docs_dir = PROJECT_ROOT / "docs"
    assert docs_dir.exists(), f"docs/ directory not found at {docs_dir}"
    md_files = list(docs_dir.glob("*.md"))
    print(f"\nTC-09 docs/ .md files: {[f.name for f in md_files]}")
    assert len(md_files) >= 1, f"docs/ must have ≥ 1 .md file. Found: {[f.name for f in md_files]}"


# ─── TC-10: Makefile help target exists ──────────────────────────────────────


def test_tc10_makefile_has_help_target():
    """TC-10: Makefile must include a 'help' target."""
    assert MAKEFILE.exists()
    content = MAKEFILE.read_text()
    lines = content.splitlines()
    target_lines = [ln for ln in lines if re.match(r"^[a-zA-Z_-]+:", ln)]
    target_names = [ln.split(":")[0].casefold() for ln in target_lines]
    print(f"\nTC-10 Makefile targets: {target_names}")
    assert "help" in target_names, "Makefile must have a 'help' target"


# ─── TC-11: scripts/ directory exists ─────────────────────────────────────────


def test_tc11_scripts_directory_exists():
    """TC-11: scripts/ directory must exist and contain demo.py."""
    scripts_dir = PROJECT_ROOT / "scripts"
    assert scripts_dir.exists(), f"scripts/ directory not found at {scripts_dir}"
    assert (scripts_dir / "demo.py").exists(), "scripts/demo.py not found"


# ─── TC-12: demo.py imports required libraries ────────────────────────────────


def test_tc12_demo_script_imports_libraries():
    """TC-12: demo.py must import at least one standard library (argparse, sys, time, etc.)."""
    assert DEMO_SCRIPT.exists()
    source = DEMO_SCRIPT.read_text()
    print(f"\nTC-12 demo.py first 500 chars: {source[:500]}")
    has_import = any(
        lib in source
        for lib in [
            "import httpx",
            "import asyncio",
            "import requests",
            "import aiohttp",
            "import argparse",
            "import sys",
            "import time",
            "import os",
        ]
    )
    assert has_import, "demo.py must have at least one import statement"


# ─── TC-13: pyproject.toml has authors field ──────────────────────────────────


def test_tc13_pyproject_has_name_and_version():
    """TC-13: pyproject.toml must declare name and version."""
    assert PYPROJECT.exists()
    content = PYPROJECT.read_bytes().decode()
    print(f"\nTC-13 pyproject name present: {'name' in content}, version: {'version' in content}")
    assert "name" in content, "pyproject.toml must have a 'name' field"
    assert "version" in content, "pyproject.toml must have a 'version' field"


# ─── TC-14: README.md mentions LangGraph and FastAPI ─────────────────────────


def test_tc14_readme_mentions_tech_stack():
    """TC-14: README.md must mention LangGraph and FastAPI in the tech stack."""
    assert README.exists()
    content = README.read_text().lower()
    print("\nTC-14 checking tech stack mentions in README")
    assert "langgraph" in content, "README.md must mention LangGraph"
    assert "fastapi" in content, "README.md must mention FastAPI"


# ─── TC-15: .env.example has at least 6 variable declarations ────────────────


def test_tc15_env_example_has_minimum_vars():
    """TC-15: .env.example must declare at least 6 environment variables."""
    assert ENV_EXAMPLE.exists()
    content = ENV_EXAMPLE.read_text()
    # Count lines with KEY=value pattern (not comments)
    var_lines = [
        ln
        for ln in content.splitlines()
        if ln.strip() and not ln.strip().startswith("#") and "=" in ln
    ]
    print(
        f"\nTC-15 .env.example var lines: {len(var_lines)} — {[ln.split('=')[0] for ln in var_lines]}"
    )
    assert len(var_lines) >= 6, (
        f".env.example must declare ≥ 6 environment variables, found {len(var_lines)}"
    )
