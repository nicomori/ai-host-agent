"""
BLOQUE 1 — Infra Base Tests (HostAI)
15 test cases covering: Dockerfile, docker-compose, Makefile, config, pyproject, src structure,
                        health endpoint, and 8 additional structural coverage cases.
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ─── TC-01: Dockerfile exists and has multi-stage build ──────────────────────
def test_tc01_dockerfile_multistage():
    """TC-01: Dockerfile must exist and contain both 'builder' and 'runtime' stages."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile not found"
    content = dockerfile.read_text()
    assert "AS builder" in content, "Missing 'AS builder' stage"
    assert "AS runtime" in content, "Missing 'AS runtime' stage"
    assert "HEALTHCHECK" in content, "Missing HEALTHCHECK instruction"
    assert "EXPOSE" in content, "Missing EXPOSE instruction"


# ─── TC-02: docker-compose.yml valid YAML with required services ──────────────
def test_tc02_docker_compose_valid():
    """TC-02: docker-compose.yml must be valid YAML and declare api, postgres, redis."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    assert compose_file.exists(), "docker-compose.yml not found"
    data = yaml.safe_load(compose_file.read_text())
    services = data.get("services", {})
    assert "api" in services, "Missing 'api' service"
    assert "postgres" in services, "Missing 'postgres' service"
    assert "redis" in services, "Missing 'redis' service"
    # healthchecks on infra services
    assert "healthcheck" in services["postgres"]
    assert "healthcheck" in services["redis"]


# ─── TC-03: Makefile has required targets ─────────────────────────────────────
def test_tc03_makefile_targets():
    """TC-03: Makefile must declare all required operational targets."""
    makefile = PROJECT_ROOT / "Makefile"
    assert makefile.exists(), "Makefile not found"
    content = makefile.read_text()
    required = ["up", "down", "logs", "test", "build", "shell", "lint", "clean"]
    for target in required:
        assert f"{target}:" in content, f"Missing Makefile target: {target}"


# ─── TC-04: config.yaml is valid and has required keys ───────────────────────
def test_tc04_config_yaml_structure():
    """TC-04: config.yaml must exist, be valid YAML, and have app/voice/llm/reservations keys."""
    config_file = PROJECT_ROOT / "config.yaml"
    assert config_file.exists(), "config.yaml not found"
    data = yaml.safe_load(config_file.read_text())
    for key in ["app", "voice", "llm", "reservations", "persistence"]:
        assert key in data, f"Missing config section: {key}"
    assert data["app"]["name"] == "ai-host-agent"


# ─── TC-05: pyproject.toml has correct metadata and key dependencies ──────────
def test_tc05_pyproject_toml():
    """TC-05: pyproject.toml must declare the project name, python>=3.11, and core deps.
    Fix: tomllib is stdlib from Python 3.11+; use try/except fallback to tomli backport,
    or fallback to raw text parsing for older Pythons (resolution form 1+4 combined).
    """
    # Resolution Form 1: try tomllib (3.11+), fallback to tomli backport
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            # Resolution Form 4: raw text parsing fallback — no external deps needed
            pyproject = PROJECT_ROOT / "pyproject.toml"
            assert pyproject.exists(), "pyproject.toml not found"
            content = pyproject.read_text()
            assert 'name = "ai-host-agent"' in content
            assert ">=3.11" in content
            for lib in ["fastapi", "langgraph", "twilio", "elevenlabs", "structlog"]:
                assert lib in content, f"Missing dependency: {lib}"
            return

    pyproject = PROJECT_ROOT / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml not found"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    project = data["project"]
    assert project["name"] == "ai-host-agent"
    assert ">=3.11" in project["requires-python"]
    deps_str = " ".join(project["dependencies"])
    for lib in ["fastapi", "langgraph", "twilio", "elevenlabs", "structlog"]:
        assert lib in deps_str, f"Missing dependency: {lib}"


# ─── TC-06: src/ directory structure is correct ───────────────────────────────
def test_tc06_src_structure():
    """TC-06: src/ must contain main.py, config.py, and required sub-packages."""
    src = PROJECT_ROOT / "src"
    assert (src / "main.py").exists(), "src/main.py not found"
    assert (src / "config.py").exists(), "src/config.py not found"
    for pkg in ["api", "agents", "tools", "services", "models"]:
        assert (src / pkg / "__init__.py").exists(), f"Missing src/{pkg}/__init__.py"


# ─── TC-07: .env.example exists and has required keys ─────────────────────────
def test_tc07_env_example():
    """TC-07: .env.example must exist and declare all critical environment variables."""
    env_example = PROJECT_ROOT / ".env.example"
    assert env_example.exists(), ".env.example not found"
    content = env_example.read_text()
    required_keys = [
        "ANTHROPIC_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "ELEVENLABS_API_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "RESTAURANT_NAME",
    ]
    for key in required_keys:
        assert key in content, f"Missing env key: {key}"


# ─── TC-08: Dockerfile has non-root USER instruction ─────────────────────────
def test_tc08_dockerfile_non_root_user():
    """TC-08: Dockerfile runtime stage must define a non-root USER."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text()
    assert "USER" in content, "Dockerfile must define a USER instruction (non-root)"


# ─── TC-09: docker-compose has restart policies ───────────────────────────────
def test_tc09_docker_compose_restart_policy():
    """TC-09: The api service in docker-compose.yml must have a restart policy."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    assert compose_file.exists()
    data = yaml.safe_load(compose_file.read_text())
    api = data["services"]["api"]
    assert "restart" in api, "api service must have a 'restart' policy"


# ─── TC-10: Makefile has 'help' target ────────────────────────────────────────
def test_tc10_makefile_has_help_target():
    """TC-10: Makefile must include a 'help' target for discoverability."""
    makefile = PROJECT_ROOT / "Makefile"
    assert makefile.exists()
    content = makefile.read_text()
    assert "help:" in content, "Makefile must have a 'help' target"


# ─── TC-11: pyproject has [tool.pytest.ini_options] section ──────────────────
def test_tc11_pyproject_pytest_section():
    """TC-11: pyproject.toml must configure pytest via [tool.pytest.ini_options]."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    assert pyproject.exists()
    content = pyproject.read_text()
    assert "pytest.ini_options" in content, "Missing [tool.pytest.ini_options] in pyproject.toml"


# ─── TC-12: src/agents directory contains required files ─────────────────────
def test_tc12_agents_package_structure():
    """TC-12: src/agents must contain graph.py, state.py, and sub_agents.py."""
    agents = PROJECT_ROOT / "src" / "agents"
    for fname in ["graph.py", "state.py", "sub_agents.py"]:
        assert (agents / fname).exists(), f"Missing src/agents/{fname}"


# ─── TC-13: .github/workflows directory exists with CI workflow ───────────────
def test_tc13_github_workflows_exist():
    """TC-13: .github/workflows must exist and contain at least ci.yml."""
    workflows = PROJECT_ROOT / ".github" / "workflows"
    assert workflows.exists(), ".github/workflows directory not found"
    assert (workflows / "ci.yml").exists(), ".github/workflows/ci.yml not found"


# ─── TC-14: docker-compose environment section includes MODEL variable ────────
def test_tc14_docker_compose_model_env():
    """TC-14: docker-compose api service environment must include LLM_MODEL or ANTHROPIC vars."""
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    assert compose_file.exists()
    raw_text = compose_file.read_text()
    data = yaml.safe_load(raw_text)
    api_service = data["services"]["api"]
    api_env = str(api_service.get("environment", [])) + str(api_service.get("env_file", []))
    # Either model or API key env var should be referenced inline or via env_file
    assert any(k in api_env for k in ["ANTHROPIC", "LLM_MODEL", "MODEL", ".env"]), (
        "api service must reference ANTHROPIC_API_KEY / LLM_MODEL or use an env_file"
    )


# ─── TC-15: tests/ directory has unit/ subdirectory with test files ───────────
def test_tc15_tests_directory_structure():
    """TC-15: tests/unit/ must exist and contain at least 5 test_*.py files."""
    tests_unit = PROJECT_ROOT / "tests" / "unit"
    assert tests_unit.exists(), "tests/unit/ directory not found"
    test_files = list(tests_unit.glob("test_*.py"))
    assert len(test_files) >= 5, f"Expected ≥ 5 test files in tests/unit/, found: {len(test_files)}"
