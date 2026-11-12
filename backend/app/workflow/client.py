"""Running one agent (feature 007, tasks T006 and T009; research R4).

An agent gets instructions, a prompt, its own read-only tools and the shape of its final answer.
The client runs the tool loop (the model asks for a tool, the toolbox answers, the model goes on)
and returns the structured answer, or raises AgentError (or TimeoutError). The real client uses
Gemini (T009); FakeAgentClient follows a script for tests, calling the real toolbox.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.workflow.tools import Toolbox

Reply = TypeVar("Reply", bound=BaseModel)


class AgentError(Exception):
    """The agent couldn't give a usable answer (API error, refusal, a forbidden tool, a reply
    in the wrong shape). The step then uses its plain result."""


class AgentClient(Protocol):  # pylint: disable=too-few-public-methods
    """Runs one agent to its final answer."""

    async def run(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        agent: str,
        instructions: str,
        prompt: str,
        tools: Toolbox,
        allowed: frozenset[str],
        reply: type[Reply],
    ) -> Reply:
        """The agent's final answer, in the shape of `reply`."""
        ...  # pylint: disable=unnecessary-ellipsis


async def call_tool(
    tools: Toolbox, allowed: frozenset[str], name: str, arguments: Mapping[str, Any]
) -> Any:
    """Run one tool the agent asked for; anything outside its own tools is refused."""
    if name not in allowed:
        raise AgentError(f"The agent asked for a tool it doesn't have: {name}.")
    try:
        return await getattr(tools, name)(**arguments)
    except TypeError as exc:
        raise AgentError(f"The agent called {name} with the wrong arguments.") from exc


@dataclass
class Script:
    """What one fake agent does: tool calls in order, then its reply (or an error to raise)."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    reply: dict[str, Any] | BaseException = field(default_factory=dict)


@dataclass
class FakeAgentClient:
    """Scripted agents for tests, keyed by agent name; records every tool call. An agent with
    no script fails, as if the AI were unavailable."""

    scripts: dict[str, Script] = field(default_factory=dict)
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    async def run(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        agent: str,
        instructions: str,
        prompt: str,
        tools: Toolbox,
        allowed: frozenset[str],
        reply: type[Reply],
    ) -> Reply:
        """Make the scripted tool calls, then return the scripted reply or raise it."""
        del instructions, prompt
        script = self.scripts.get(agent)
        if script is None:
            raise AgentError("No AI in tests.")
        for name, arguments in script.calls:
            self.calls.append((agent, name, arguments))
            await call_tool(tools, allowed, name, arguments)
        if isinstance(script.reply, BaseException):
            raise script.reply
        try:
            return reply.model_validate(script.reply)
        except ValidationError as exc:
            raise AgentError("The reply wasn't in the expected form.") from exc
