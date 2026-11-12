"""deploy/deploy.sh, the only command the deploy key may run on the VM (feature 001, User Story 5,
task T045; FR-024, FR-025; docs/superpowers/specs/2026-11-10-continuous-deployment-design.md).

The real script runs against stub `git` and `docker` commands that record their arguments (and,
for `docker login`, what arrived on standard input), so nothing real is touched.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy.sh"
SHA = "0123456789abcdef0123456789abcdef01234567"
TOKEN = "ghs_secret_token_value_for_tests"
STUB = """#!/usr/bin/env bash
# Record the call; for `docker login`, also what came on standard input.
echo "$(basename "$0") $* | DOCKER_CONFIG=${DOCKER_CONFIG:-} IMAGE_TAG=${IMAGE_TAG:-}" >> "$CALLS"
if [ "$1" = "login" ]; then cat > "$CALLS.stdin"; fi
if [ -n "${FAIL_ON:-}" ] && [[ "$*" == *"$FAIL_ON"* ]]; then exit 1; fi
exit 0
"""


def posix(path: Path) -> str:
    """The path as bash sees it (Git Bash on Windows wants /c/Users/..., not a drive letter)."""
    if os.name != "nt":
        return str(path)
    return "/" + path.drive[0].lower() + path.as_posix()[2:]


def bash() -> str:
    """Git Bash on Windows (plain `bash` there is WSL's), `bash` elsewhere."""
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            for folder in Path(git).resolve().parents:
                candidate = folder / "bin" / "bash.exe"
                if candidate.exists():
                    return str(candidate)
        raise RuntimeError("Git Bash not found.")
    return "bash"


@pytest.fixture(name="app")
def app_dir(tmp_path: Path) -> Path:
    """A copy of the app folder layout: the script in deploy/, stub tools in bin/."""
    app = tmp_path / "pak-tax-filer"
    (app / "deploy").mkdir(parents=True)
    shutil.copy(SCRIPT, app / "deploy" / "deploy.sh")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("git", "docker"):
        stub = bin_dir / tool
        stub.write_text(STUB, encoding="utf-8", newline="\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return app


def run(
    app: Path, command: str, token: str | None = TOKEN, fail_on: str | None = None
) -> tuple[subprocess.CompletedProcess[str], list[str], str]:
    """Run deploy.sh as the forced command would: the request in SSH_ORIGINAL_COMMAND."""
    calls = app.parent / "calls.log"
    env = {
        **os.environ,
        "STUB_BIN": posix(app.parent / "bin"),
        "SSH_ORIGINAL_COMMAND": command,
        "CALLS": str(calls),
    }
    if fail_on:
        env["FAIL_ON"] = fail_on
    # The stubs go first on PATH inside bash itself: Git Bash on Windows rebuilds PATH on start.
    result = subprocess.run(
        [
            bash(),
            "-c",
            'PATH="$STUB_BIN:$PATH" exec bash "$0"',
            posix(app / "deploy" / "deploy.sh"),
        ],
        input="" if token is None else token + "\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    lines = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    stdin = (
        calls.with_name("calls.log.stdin").read_text(encoding="utf-8")
        if calls.with_name("calls.log.stdin").exists()
        else ""
    )
    return result, lines, stdin


def test_a_good_request_checks_out_pulls_and_starts_that_commit(app: Path) -> None:
    """Fails if the deploy doesn't fetch and check out the commit (so the compose file matches
    the images), pull both images for it, and start them without building."""
    result, calls, _ = run(app, f"deploy {SHA} merger")

    assert result.returncode == 0, result.stderr
    assert all(
        f"-C {posix(app)} " in c for c in calls if c.startswith("git ")
    )  # this app folder
    assert any(c.startswith("git ") and "fetch" in c and SHA in c for c in calls)
    assert any(c.startswith("git ") and "checkout" in c and SHA in c for c in calls)
    pull = next(c for c in calls if " pull " in c)
    up = next(c for c in calls if " up " in c)
    assert "backend" in pull and "web" in pull
    assert f"IMAGE_TAG={SHA}" in pull and f"IMAGE_TAG={SHA}" in up
    assert "--no-build" in up
    assert "docker-compose.prod.yml" in pull and "docker-compose.prod.yml" in up
    assert calls.index(pull) < calls.index(up)


def test_the_token_goes_only_to_docker_login_on_standard_input(app: Path) -> None:
    """Fails if the registry token appears on any command line or in the output (FR-025)."""
    result, calls, stdin = run(app, f"deploy {SHA} merger")

    assert result.returncode == 0, result.stderr
    login = next(c for c in calls if c.startswith("docker login"))
    assert "ghcr.io" in login and "--password-stdin" in login and "-u merger" in login
    assert stdin.strip() == TOKEN
    assert all(TOKEN not in call for call in calls)
    assert TOKEN not in result.stdout + result.stderr


def test_the_registry_login_is_temporary_even_when_a_step_fails(app: Path) -> None:
    """Fails if the login is saved where it outlives the deploy (e.g. ~/.docker), or is left
    behind when a pull fails."""
    result, calls, _ = run(app, f"deploy {SHA} merger", fail_on="pull")

    assert result.returncode != 0
    config = next(c for c in calls if c.startswith("docker login")).split(
        "DOCKER_CONFIG="
    )[1]
    config = config.split(" ")[0]
    assert config and not Path(config).exists()
    assert not any(" up " in c for c in calls)


@pytest.mark.parametrize(
    "command",
    [
        "whoami",  # any other command
        "",  # a plain `ssh host` (a shell)
        f"deploy {SHA[:-1]} merger",  # too short
        f"deploy {SHA.upper()} merger",  # not lower-case hex
        f"deploy {SHA}; rm -rf / merger",  # an injection attempt
        f"deploy {SHA} merger extra",  # anything more
        f"deploy {SHA} bad;user",  # a name that isn't a GitHub login
        f"deploy {SHA}",  # no name
    ],
)
def test_anything_but_a_deploy_request_is_refused_before_anything_runs(
    app: Path, command: str
) -> None:
    """Fails if the deploy key could run any other command, or a malformed request reaches git
    or docker (FR-024)."""
    result, calls, _ = run(app, command)

    assert result.returncode != 0
    assert calls == []
    assert "Refused" in result.stderr


def test_no_token_is_refused_before_anything_runs(app: Path) -> None:
    """Fails if a deploy without a registry token goes ahead (it couldn't pull private images)."""
    result, calls, _ = run(app, f"deploy {SHA} merger", token=None)

    assert result.returncode != 0
    assert calls == []


def test_a_bot_login_is_accepted(app: Path) -> None:
    """Fails if a merge made by a GitHub bot account (name ending in [bot]) can't deploy."""
    result, _, _ = run(app, f"deploy {SHA} github-actions[bot]")

    assert result.returncode == 0, result.stderr
