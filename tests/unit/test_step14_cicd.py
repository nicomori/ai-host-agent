"""
Step 14 — CI/CD + GitHub Actions: Test Suite (ai-host-agent)

7 test cases covering:
  TC-01: ci.yml exists and is valid YAML
  TC-02: ci.yml triggers on push + pull_request events
  TC-03: ci.yml has a lint job with ruff steps
  TC-04: ci.yml has a test job with pytest step
  TC-05: ci.yml has a docker-build job
  TC-06: cd.yml exists and has build-and-push job with docker metadata action
  TC-07: Dockerfile has required multi-stage build (builder + runtime targets)

Error resolutions applied:
  Form 1: YAML loaded with yaml.safe_load (no-exec, safe parsing)
  Form 2: jobs accessed via dict key lookup with .get() default to {}
  Form 3: step names searched case-insensitively via .lower() string matching
  Form 4: Dockerfile parsed line-by-line without shell execution
  Form 5: pytest.importorskip guards protect against missing yaml module
"""
from __future__ import annotations

import pathlib

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS_DIR / "ci.yml"
CD_WORKFLOW = WORKFLOWS_DIR / "cd.yml"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"


def _load_yaml(path: pathlib.Path) -> dict:
    """Load a YAML file safely. Form 1: yaml.safe_load."""
    yaml = pytest.importorskip("yaml")  # Form 5: guard
    return yaml.safe_load(path.read_text())


def _get_triggers(workflow: dict) -> dict:
    """
    Extract the 'on' triggers from a workflow dict.
    Form 2: PyYAML parses YAML 'on' keyword as Python True (bool).
    Handle both the string key "on" and the boolean key True.
    """
    return workflow.get("on", workflow.get(True, {}))


# ─── TC-01: ci.yml exists and is valid YAML ───────────────────────────────────

def test_tc01_ci_workflow_exists_and_valid_yaml():
    """TC-01: .github/workflows/ci.yml must exist and parse as valid YAML."""
    assert CI_WORKFLOW.exists(), f"ci.yml not found at {CI_WORKFLOW}"
    workflow = _load_yaml(CI_WORKFLOW)
    print(f"\nTC-01 ci.yml top-level keys: {list(workflow.keys())}")
    assert isinstance(workflow, dict)
    assert "name" in workflow
    # Form 2: PyYAML maps 'on' keyword to True — accept both
    assert "on" in workflow or True in workflow, "Workflow must have 'on' triggers"
    assert "jobs" in workflow


# ─── TC-02: ci.yml triggers on push + pull_request ────────────────────────────

def test_tc02_ci_triggers_push_and_pr():
    """TC-02: CI workflow must trigger on push and pull_request events."""
    workflow = _load_yaml(CI_WORKFLOW)
    # Form 2: _get_triggers handles PyYAML 'on' → True coercion
    triggers = _get_triggers(workflow)
    print(f"\nTC-02 triggers: {triggers}")
    assert isinstance(triggers, dict), "'on' must be a dict of event→config"
    assert "push" in triggers, "CI must trigger on 'push'"
    assert "pull_request" in triggers, "CI must trigger on 'pull_request'"
    push_branches = triggers["push"].get("branches", [])
    pr_branches = triggers["pull_request"].get("branches", [])
    assert any(b in push_branches for b in ["main", "master"]), \
        "push trigger must include main/master"
    assert any(b in pr_branches for b in ["main", "master"]), \
        "pull_request trigger must include main/master"


# ─── TC-03: ci.yml has lint job with ruff ─────────────────────────────────────

def test_tc03_ci_has_lint_job_with_ruff():
    """TC-03: CI workflow must have a lint job that runs ruff."""
    workflow = _load_yaml(CI_WORKFLOW)
    jobs = workflow.get("jobs", {})  # Form 2: safe .get()
    print(f"\nTC-03 jobs: {list(jobs.keys())}")
    assert "lint" in jobs, "CI must have a 'lint' job"
    lint_job = jobs["lint"]
    steps = lint_job.get("steps", [])
    # Form 3: case-insensitive name search
    step_runs = [s.get("run", "") for s in steps]
    has_ruff = any("ruff" in (r or "").lower() for r in step_runs)
    assert has_ruff, f"lint job must run ruff. Got: {step_runs}"


# ─── TC-04: ci.yml has test job with pytest ────────────────────────────────────

def test_tc04_ci_has_test_job_with_pytest():
    """TC-04: CI workflow must have a test job that runs pytest."""
    workflow = _load_yaml(CI_WORKFLOW)
    jobs = workflow.get("jobs", {})
    print(f"\nTC-04 jobs: {list(jobs.keys())}")
    assert "test" in jobs, "CI must have a 'test' job"
    test_job = jobs["test"]
    steps = test_job.get("steps", [])
    step_runs = [s.get("run", "") for s in steps]
    has_pytest = any("pytest" in (r or "").lower() for r in step_runs)
    assert has_pytest, f"test job must run pytest. Got: {step_runs}"
    # Test job must depend on lint
    needs = test_job.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    assert "lint" in needs, "test job must 'needs: lint'"


# ─── TC-05: ci.yml has docker-build job ──────────────────────────────────────

def test_tc05_ci_has_docker_build_job():
    """TC-05: CI workflow must have a docker-build job that does NOT push."""
    workflow = _load_yaml(CI_WORKFLOW)
    jobs = workflow.get("jobs", {})
    print(f"\nTC-05 jobs: {list(jobs.keys())}")
    assert "docker-build" in jobs, "CI must have a 'docker-build' job"
    docker_job = jobs["docker-build"]
    steps = docker_job.get("steps", [])
    # Verify no push=true in any step
    for step in steps:
        step_with = step.get("with", {}) or {}
        push_val = step_with.get("push", None)
        if push_val is not None:
            assert push_val is False, \
                f"docker-build CI job must NOT push (push: false). Got: {push_val}"
    print("\nTC-05 docker-build job has no push=true ✓")


# ─── TC-06: cd.yml has build-and-push job with metadata action ────────────────

def test_tc06_cd_has_build_and_push_job():
    """TC-06: cd.yml must have build-and-push job with docker metadata action."""
    assert CD_WORKFLOW.exists(), f"cd.yml not found at {CD_WORKFLOW}"
    workflow = _load_yaml(CD_WORKFLOW)
    jobs = workflow.get("jobs", {})
    print(f"\nTC-06 cd.yml jobs: {list(jobs.keys())}")
    assert "build-and-push" in jobs, "CD must have a 'build-and-push' job"
    bp_job = jobs["build-and-push"]
    steps = bp_job.get("steps", [])
    uses_list = [s.get("uses", "") for s in steps]
    print(f"\nTC-06 uses: {uses_list}")
    # Must use docker metadata action and build-push action
    has_metadata = any("metadata-action" in (u or "") for u in uses_list)
    has_build_push = any("build-push-action" in (u or "") for u in uses_list)
    assert has_metadata, "build-and-push must use docker/metadata-action"
    assert has_build_push, "build-and-push must use docker/build-push-action"


# ─── TC-07: Dockerfile has multi-stage build ─────────────────────────────────

def test_tc07_dockerfile_has_multi_stage_build():
    """TC-07: Dockerfile must define both builder and runtime stages."""
    assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"
    # Form 4: parse Dockerfile line-by-line (no shell execution)
    lines = DOCKERFILE.read_text().splitlines()
    from_lines = [ln.strip() for ln in lines if ln.strip().upper().startswith("FROM")]
    print(f"\nTC-07 FROM lines: {from_lines}")
    # Must have at least 2 stages (multi-stage build)
    assert len(from_lines) >= 2, \
        f"Dockerfile must have ≥2 FROM statements (multi-stage). Got: {from_lines}"
    # Stages must include 'builder' and 'runtime' targets
    as_names = [ln.split(" AS ")[-1].strip().lower() for ln in from_lines if " AS " in ln.upper()]
    print(f"\nTC-07 stage names: {as_names}")
    assert "builder" in as_names, "Dockerfile must define 'builder' stage"
    assert "runtime" in as_names, "Dockerfile must define 'runtime' stage"


# ─── TC-08: ci.yml lint job has checkout step ────────────────────────────────

def test_tc08_ci_lint_job_has_checkout():
    """TC-08: CI lint job must have a checkout step (actions/checkout)."""
    workflow = _load_yaml(CI_WORKFLOW)
    lint_steps = workflow.get("jobs", {}).get("lint", {}).get("steps", [])
    uses_list = [s.get("uses", "") or "" for s in lint_steps]
    print(f"\nTC-08 lint uses: {uses_list}")
    assert any("actions/checkout" in u for u in uses_list), \
        "lint job must include an actions/checkout step"


# ─── TC-09: cd.yml triggers on push to main or release event ─────────────────

def test_tc09_cd_triggers_on_release_or_tag():
    """TC-09: cd.yml must trigger on release publish or tag push."""
    assert CD_WORKFLOW.exists(), f"cd.yml not found at {CD_WORKFLOW}"
    workflow = _load_yaml(CD_WORKFLOW)
    triggers = _get_triggers(workflow)
    print(f"\nTC-09 cd.yml triggers: {triggers}")
    has_release = "release" in triggers
    has_tag_push = (
        "push" in triggers
        and any(
            t.startswith("v") or t.startswith("refs/tags")
            for t in triggers["push"].get("tags", [])
        )
    )
    assert has_release or has_tag_push, (
        "cd.yml must trigger on 'release' event or tag push"
    )


# ─── TC-10: ci.yml test job has checkout step ────────────────────────────────

def test_tc10_ci_test_job_has_checkout():
    """TC-10: CI test job must include actions/checkout step."""
    workflow = _load_yaml(CI_WORKFLOW)
    test_steps = workflow.get("jobs", {}).get("test", {}).get("steps", [])
    uses_list = [s.get("uses", "") or "" for s in test_steps]
    print(f"\nTC-10 test uses: {uses_list}")
    assert any("actions/checkout" in u for u in uses_list), \
        "test job must include an actions/checkout step"


# ─── TC-11: Dockerfile has EXPOSE instruction ─────────────────────────────────

def test_tc11_dockerfile_has_expose():
    """TC-11: Dockerfile must contain an EXPOSE instruction."""
    assert DOCKERFILE.exists()
    content = DOCKERFILE.read_text()
    lines = [ln.strip() for ln in content.splitlines()]
    expose_lines = [ln for ln in lines if ln.upper().startswith("EXPOSE")]
    print(f"\nTC-11 EXPOSE lines: {expose_lines}")
    assert expose_lines, "Dockerfile must have at least one EXPOSE instruction"


# ─── TC-12: ci.yml uses setup-python action ──────────────────────────────────

def test_tc12_ci_uses_setup_python():
    """TC-12: CI workflow must use actions/setup-python in at least one job."""
    workflow = _load_yaml(CI_WORKFLOW)
    all_uses = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            uses = step.get("uses", "") or ""
            if uses:
                all_uses.append(uses)
    print(f"\nTC-12 all uses: {all_uses}")
    assert any("setup-python" in u for u in all_uses), \
        "CI workflow must use actions/setup-python"


# ─── TC-13: ci.yml docker-build needs test ───────────────────────────────────

def test_tc13_docker_build_needs_test():
    """TC-13: docker-build job must depend on test (needs: test)."""
    workflow = _load_yaml(CI_WORKFLOW)
    docker_job = workflow.get("jobs", {}).get("docker-build", {})
    needs = docker_job.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    print(f"\nTC-13 docker-build needs: {needs}")
    assert "test" in needs, "docker-build job must 'needs: test'"


# ─── TC-14: cd.yml uses secrets for Docker Hub ───────────────────────────────

def test_tc14_cd_uses_secrets_for_docker():
    """TC-14: cd.yml build-and-push job must reference Docker Hub secrets."""
    assert CD_WORKFLOW.exists()
    workflow = _load_yaml(CD_WORKFLOW)
    cd_text = (CD_WORKFLOW).read_text()
    print(f"\nTC-14 checking secrets in cd.yml (first 500 chars): {cd_text[:500]}")
    has_dockerhub = any(
        term in cd_text for term in ["DOCKERHUB_USERNAME", "DOCKER_USERNAME", "REGISTRY_USERNAME"]
    )
    has_token = any(
        term in cd_text for term in ["DOCKERHUB_TOKEN", "DOCKER_PASSWORD", "REGISTRY_TOKEN", "REGISTRY_PASSWORD"]
    )
    assert has_dockerhub, "cd.yml must reference a Docker Hub username secret"
    assert has_token, "cd.yml must reference a Docker Hub token/password secret"


# ─── TC-15: ci.yml runs ruff format or ruff check ────────────────────────────

def test_tc15_ci_ruff_has_format_or_check():
    """TC-15: CI lint job must run ruff with either 'check' or 'format --check'."""
    workflow = _load_yaml(CI_WORKFLOW)
    lint_steps = workflow.get("jobs", {}).get("lint", {}).get("steps", [])
    runs = " ".join(s.get("run", "") or "" for s in lint_steps)
    print(f"\nTC-15 lint runs combined: {runs[:300]}")
    has_ruff_check = "ruff check" in runs
    has_ruff_format = "ruff format" in runs
    assert has_ruff_check or has_ruff_format, \
        f"lint job must run 'ruff check' or 'ruff format'. Got: {runs[:200]}"
