"""
Agent state definitions and utilities.

This module defines the state structures used by agents in the framework.
It provides TypedDict-based state definitions with helper functions for
state manipulation and updates.

The state design follows LangGraph patterns with:
- TypedDict for type safety
- Annotated fields for reducer functions
- Helper functions for state operations
"""

from operator import add
from typing import Any, TypedDict, Optional, Union

from langchain_core.messages import MessageLikeRepresentation


# Type alias for message representations (allows various message formats)
MessagesList = list[MessageLikeRepresentation]


class AgentState(TypedDict, total=False):
    """Base state for all agents.

    This state provides common fields that most agents will need:
    - messages: Conversation history for context
    - metadata: Agent-specific metadata
    - output: Final output from the agent
    - errors: List of errors encountered during execution

    Agents can extend this state with additional fields as needed.
    All fields are optional (total=False) to allow partial initialization.
    """

    # Conversation messages for context and history
    messages: MessagesList

    # Agent-specific metadata (can store intermediate results, flags, etc.)
    metadata: dict[str, Any]

    # Final output from the agent (type depends on agent type)
    output: Optional[str]

    # List of errors encountered during execution
    errors: list[str]

    # Additional custom fields can be added by extending agents


class NewsletterAgentState(AgentState):
    """State specific to the newsletter generation agent.

    Extends AgentState with newsletter-specific fields:
    - raw_articles: Articles collected from web scraping
    - research_summary: Summary generated from article analysis
    - key_insights: Key insights extracted from research
    - opinion_analysis: Analysis of opinions and trends
    - final_newsletter: The generated newsletter content
    """

    # Articles collected from various sources
    raw_articles: list[dict[str, Any]]

    # Research phase output
    research_summary: str

    # Analysis phase output
    key_insights: str

    # Opinion writing phase output
    opinion_analysis: str

    # Final newsletter content (primary output)
    final_newsletter: str


class DeepResearchAgentState(AgentState):
    """State specific to the deep research agent.

    Extends AgentState with deep research-specific fields:
    - research_brief: The research brief/question
    - supervisor_messages: Messages for the supervisor subgraph
    - notes: Final research notes/findings
    - raw_notes: Raw notes before compression
    - final_report: Final research report
    - iterations_count: Number of research iterations performed
    """

    # Research brief/question from user
    research_brief: str

    # Supervisor subgraph messages
    supervisor_messages: MessagesList

    # Compressed research notes/findings
    notes: list[str]

    # Raw notes before compression
    raw_notes: list[str]

    # Final comprehensive research report
    final_report: str

    # Iteration tracking
    iterations_count: int


class ResearchUnitState(TypedDict, total=False):
    """State for individual research units (sub-agents).

    Used by the deep research supervisor to manage parallel research tasks.
    Each research unit operates on a specific topic or sub-question.
    """

    # Research topic for this unit
    research_topic: str

    # Messages for the research unit
    researcher_messages: MessagesList

    # Compressed research output
    compressed_research: str

    # Tool call iteration count
    tool_call_iterations: int

    # Raw notes collected during research
    raw_notes: list[str]


def create_initial_state(
    state_class: type[AgentState],
    **kwargs: Any,
) -> AgentState:
    """Create an initial state with default values.

    This function creates a new state instance with sensible defaults
    for all required fields. Additional fields can be passed as kwargs.

    Args:
        state_class: The state class to instantiate
        **kwargs: Additional fields to initialize

    Returns:
        A new state instance with default values

    Example:
        state = create_initial_state(
            NewsletterAgentState,
            raw_articles=[],
            research_summary="",
        )
    """
    # Initialize with common defaults
    initial: AgentState = {
        "messages": [],
        "metadata": {},
        "errors": [],
    }

    # Add any provided fields
    for key, value in kwargs.items():
        if key in state_class.__annotations__:
            initial[key] = value

    return initial


def merge_state_updates(
    current: AgentState,
    updates: dict[str, Any],
) -> AgentState:
    """Merge updates into the current state.

    This function handles state updates with proper merging behavior:
    - Lists are extended rather than replaced
    - Dictionaries are deep-merged
    - Other values are replaced

    Args:
        current: The current state
        updates: The updates to apply

    Returns:
        The merged state

    Example:
        new_state = merge_state_updates(current_state, {
            "messages": [new_message],
            "metadata": {"step": 2},
        })
    """
    result = current.copy()

    for key, value in updates.items():
        if key not in result:
            result[key] = value
            continue

        # Handle list merging
        if isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        # Handle dict merging
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = {**result[key], **value}
        # Otherwise replace
        else:
            result[key] = value

    return result


def override_reducer(
    current: list[Any],
    new: Union[list[Any], dict[str, Any]],
) -> list[Any]:
    """Reducer that allows overriding values in state.

    This reducer is used for fields that should be replaced rather than
    accumulated. It checks if the new value is an override directive
    and handles it appropriately.

    Args:
        current: The current list value
        new: The new value (either a list or override directive)

    Returns:
        The updated list
    """
    # Check for override directive
    if isinstance(new, dict) and new.get("type") == "override":
        return new.get("value", current)
    # Otherwise accumulate
    return add(current, new)


# Export common reducer for use in agent definitions
list_reducer = add
"""Default reducer for list fields - accumulates items."""

str_reducer = lambda c, n: (c or "") + (n or "")
"""Reducer for string fields - concatenates strings."""