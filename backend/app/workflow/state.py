"""The run's transitions (feature 007, task T004; research R2, data-model.md "Transitions").

A pure function: no database, clock or AI. The service records the step it returns; anything
the table doesn't allow raises InvalidTransition, so a run can't approve away from the gate or
reach the result without an approval for exactly its current inputs (Principle III).
"""

import enum

from app.workflow.models import Step


class Event(enum.StrEnum):
    """What can happen to a run."""

    START = "start"
    STEPS_OK = "steps_ok"
    MISSING_SALARY = "missing_salary"
    APPROVE = "approve"
    BACK = "back"
    MARK_DONE = "mark_done"
    INPUTS_CHANGED = "inputs_changed"


class InvalidTransition(Exception):
    """The event isn't allowed at this step."""


_AGENT_ORDER = {
    Step.DOCUMENT: Step.VALIDATE,
    Step.VALIDATE: Step.RESEARCH,
    Step.RESEARCH: Step.GATE,
}

# (step, event) -> new step, for the events that need no check beyond the step itself.
_TABLE: dict[tuple[Step, Event], Step] = {
    **{(step, Event.STEPS_OK): after for step, after in _AGENT_ORDER.items()},
    (Step.DOCUMENT, Event.MISSING_SALARY): Step.DOCUMENT,
    (Step.GATE, Event.APPROVE): Step.RESULT,
    (Step.GATE, Event.BACK): Step.DOCUMENT,
}


def next_step(
    step: Step | None,
    event: Event,
    *,
    approved: str | None = None,
    current: str | None = None,
) -> Step:
    """The step after this event, or InvalidTransition. `step` is None before the first start;
    `approved` and `current` are the approval's and the inputs' fingerprints."""
    if event is Event.START:
        return Step.DOCUMENT  # a new run, a restart, or after done: the row is reset
    if step is not None and event is Event.INPUTS_CHANGED:
        return Step.DOCUMENT  # steps 1-3 re-run on the new inputs; the approval is cleared
    if step is Step.RESULT and event is Event.MARK_DONE:
        if not result_allowed(step, approved, current):
            raise InvalidTransition("The approval was for other inputs.")
        return Step.DONE
    if step is not None and (step, event) in _TABLE:
        return _TABLE[(step, event)]
    raise InvalidTransition(f"{event.value} isn't allowed at {step.value if step else 'no run'}.")


def result_allowed(step: Step, approved: str | None, current: str | None) -> bool:
    """True only at the result (or done) with an approval for exactly the current inputs."""
    return step in (Step.RESULT, Step.DONE) and current is not None and approved == current
