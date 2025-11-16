"""Custom TodoListMiddleware that fixes the todos state to allow multiple updates per step."""

from typing import Annotated, Literal

from langchain.agents.middleware import TodoListMiddleware
from langchain.agents.middleware.types import AgentState
from typing_extensions import NotRequired, TypedDict


class Todo(TypedDict):
    """A single todo item with content and status."""

    content: str
    """The content/description of the todo item."""

    status: Literal["pending", "in_progress", "completed"]
    """The current status of the todo item."""


def _merge_todos(current: list[Todo] | None, update: list[Todo] | None) -> list[Todo]:
    """Merge todo updates - takes the last update when multiple nodes update in the same step.
    
    LangGraph will call this reducer sequentially for each update in the same step.
    By returning the update, we ensure the last update wins (which is the desired behavior
    since write_todos expects to replace the entire todo list).
    """
    # For write_todos, we always want to replace the entire list with the new one
    # So we just return the update (last update wins)
    # Handle None case for initial state
    if update is not None:
        return update
    return current or []


class PlanningState(AgentState):
    """State schema for the todo middleware with proper Annotated type for multiple updates."""

    todos: NotRequired[Annotated[list[Todo], _merge_todos]]
    """List of todo items for tracking task progress. Supports multiple updates per step."""


class FixedTodoListMiddleware(TodoListMiddleware):
    """TodoListMiddleware with fixed state definition to allow multiple updates per step.
    
    This fixes the InvalidUpdateError that occurs when multiple nodes try to update
    the todos key in the same step. The original TodoListMiddleware defines todos
    as a regular list, which doesn't support multiple concurrent updates.
    """

    state_schema = PlanningState

