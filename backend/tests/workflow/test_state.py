"""The run's transitions (feature 007, task T004; research R2, data-model.md "Transitions").

A pure function, so every step and event pair is tested without a database or any AI.
"""

import pytest

from app.workflow.models import Step
from app.workflow.state import Event, InvalidTransition, next_step, result_allowed

FP = "a" * 64
OTHER = "b" * 64
ALL_STEPS = list(Step)


@pytest.mark.parametrize("step", [None, *ALL_STEPS])
def test_start_always_begins_at_the_document_step(step: Step | None) -> None:
    """Fails if starting (or restarting, or after done) doesn't reset the run to step 1."""
    assert next_step(step, Event.START) is Step.DOCUMENT


def test_the_agent_steps_go_in_order_to_the_gate() -> None:
    """Fails if a step can be skipped or the order changes (document, validate, research)."""
    assert next_step(Step.DOCUMENT, Event.STEPS_OK) is Step.VALIDATE
    assert next_step(Step.VALIDATE, Event.STEPS_OK) is Step.RESEARCH
    assert next_step(Step.RESEARCH, Event.STEPS_OK) is Step.GATE


def test_a_missing_salary_certificate_stays_at_the_document_step() -> None:
    """Fails if a run without a confirmed salary certificate can move on (FR-003)."""
    assert next_step(Step.DOCUMENT, Event.MISSING_SALARY) is Step.DOCUMENT


def test_at_the_gate_approve_goes_to_the_result_and_back_to_the_start() -> None:
    """Fails if the gate's two choices lead anywhere else."""
    assert next_step(Step.GATE, Event.APPROVE) is Step.RESULT
    assert next_step(Step.GATE, Event.BACK) is Step.DOCUMENT


def test_marking_done_needs_a_current_approval() -> None:
    """Fails if a run can be finished on an approval given for other inputs (FR-009)."""
    assert next_step(Step.RESULT, Event.MARK_DONE, approved=FP, current=FP) is Step.DONE
    with pytest.raises(InvalidTransition):
        next_step(Step.RESULT, Event.MARK_DONE, approved=FP, current=OTHER)
    with pytest.raises(InvalidTransition):
        next_step(Step.RESULT, Event.MARK_DONE, approved=None, current=FP)


@pytest.mark.parametrize("step", ALL_STEPS)
def test_changed_inputs_always_re_run_from_the_document_step(step: Step) -> None:
    """Fails if any step, even done, survives a change to the inputs (FR-013)."""
    assert next_step(step, Event.INPUTS_CHANGED) is Step.DOCUMENT


@pytest.mark.parametrize(
    ("step", "event"),
    [
        *[(s, Event.APPROVE) for s in ALL_STEPS if s is not Step.GATE],
        *[(s, Event.BACK) for s in ALL_STEPS if s is not Step.GATE],
        *[(s, Event.MARK_DONE) for s in ALL_STEPS if s is not Step.RESULT],
        *[(s, Event.STEPS_OK) for s in (Step.GATE, Step.RESULT, Step.DONE)],
        *[(s, Event.MISSING_SALARY) for s in ALL_STEPS if s is not Step.DOCUMENT],
        (None, Event.APPROVE),
    ],
)
def test_every_other_pair_is_refused(step: Step | None, event: Event) -> None:
    """Fails if an event can move a run from a step the transitions table doesn't allow, e.g.
    approving away from the gate (Principle III)."""
    with pytest.raises(InvalidTransition):
        next_step(step, event, approved=FP, current=FP)


@pytest.mark.parametrize(
    ("step", "approved", "current", "allowed"),
    [
        (Step.RESULT, FP, FP, True),
        (Step.DONE, FP, FP, True),
        (Step.RESULT, FP, OTHER, False),  # inputs changed since the approval
        (Step.RESULT, None, FP, False),
        (Step.GATE, FP, FP, False),  # not yet at the result
        (Step.RESULT, FP, None, False),  # no inputs (no profile)
    ],
)
def test_the_result_only_with_a_current_approval(
    step: Step, approved: str | None, current: str | None, allowed: bool
) -> None:
    """Fails if the result could be shown without an approval for exactly these inputs."""
    assert result_allowed(step, approved, current) is allowed
