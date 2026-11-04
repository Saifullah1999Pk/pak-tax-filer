"""tax-rates-guard.sh, per specs/001-repo-foundations/contracts/claude-hooks.md (FR-008, FR-009).

Run: uv run --no-project --with pytest pytest .claude/hooks/tests
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "tax-rates-guard.sh"
REASON = (
    "Tax-rates module: rates must come from FBR's gazetted documents (constitution, Principle II). "
    "Approve only if this change cites its FBR source."
)


def bash() -> str:
    """Git Bash on Windows (plain `bash` there is WSL's), `bash` elsewhere.

    Claude Code runs hooks with Git Bash on Windows, so the tests do too.
    """
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            # git.exe sits in Git\cmd, Git\bin or Git\mingw64\bin; bash.exe is in Git\bin.
            for folder in Path(git).resolve().parents:
                candidate = folder / "bin" / "bash.exe"
                if candidate.exists():
                    return str(candidate)
        raise RuntimeError(
            "Git Bash not found; Claude Code on Windows needs Git for Windows."
        )
    return "bash"


def run_hook(event: dict[str, object]) -> subprocess.CompletedProcess[str]:
    """Feed one Claude Code PreToolUse event to the hook on standard input."""
    return subprocess.run(
        [bash(), str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def edit_event(tool: str, file_path: str) -> dict[str, object]:
    """A PreToolUse event for a file-editing tool."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
    }


def bash_event(command: str) -> dict[str, object]:
    """A PreToolUse event for the Bash tool."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


INSIDE_PATHS = [
    "/home/dev/pak-tax-filer/backend/app/tax/rates/ty2026.py",
    "C:\\Users\\dev\\pak-tax-filer\\backend\\app\\tax\\rates\\ty2026.py",
    "C:/Users/dev/pak-tax-filer/backend/app/tax/rates/__init__.py",
]
OUTSIDE_PATHS = [
    "/home/dev/pak-tax-filer/backend/app/main.py",
    "/home/dev/pak-tax-filer/backend/app/tax/engine.py",
    # A name that merely starts with "rates" is not the guarded folder.
    "/home/dev/pak-tax-filer/backend/app/tax/ratesheet.py",
]


def assert_asks_with_fbr_reason(result: subprocess.CompletedProcess[str]) -> None:
    """The hook must ask (never deny) and give the contract's FBR reason."""
    assert result.returncode == 0
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "ask"
    assert output["permissionDecisionReason"] == REASON


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
@pytest.mark.parametrize("file_path", INSIDE_PATHS)
def test_editing_a_rates_file_asks(tool: str, file_path: str) -> None:
    """Fails if any edit inside backend/app/tax/rates/ goes through without a prompt."""
    assert_asks_with_fbr_reason(run_hook(edit_event(tool, file_path)))


@pytest.mark.parametrize(
    "command",
    [
        "sed -i 's/0.05/0.06/' backend/app/tax/rates/ty2026.py",
        "echo x > backend\\app\\tax\\rates\\ty2026.py",
    ],
)
def test_shell_command_touching_rates_asks(command: str) -> None:
    """Fails if a shell command naming the rates folder (either slash) runs without a prompt."""
    assert_asks_with_fbr_reason(run_hook(bash_event(command)))


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
@pytest.mark.parametrize("file_path", OUTSIDE_PATHS)
def test_editing_other_files_is_left_alone(tool: str, file_path: str) -> None:
    """Fails if the guard interferes with files outside the rates folder."""
    result = run_hook(edit_event(tool, file_path))
    assert result.returncode == 0
    assert result.stdout == ""


def test_other_shell_commands_are_left_alone() -> None:
    """Fails if the guard interferes with ordinary shell commands."""
    result = run_hook(bash_event("uv run pytest backend/tests"))
    assert result.returncode == 0
    assert result.stdout == ""
