"""
State definitions for the deep research agent.

This module defines the state structures used by the deep research
agent. It follows the multi-state pattern from LangGraph where
different sub-components have their own state definitions.

States:
- AgentState: Main entry point state
- SupervisorState: State for the research supervisor
- ResearcherState: State for individual research units
"""

from operator import add
from typing import Annotated, Any, Optional

from langchain_core.messages import MessageLikeRepresentation
from typing_extensions import TypedDict


def override_reducer(
    current: list[Any],
    new: list[Any] | dict[str, Any],
) -> list[Any]:
    """Reducer that allows overriding values in state.

    Used for fields that should be replaced rather than accumulated.
    Checks for override directive in dict format.

    Args:
        current: Current list value
        new: New value (list or override directive)

    Returns:
        Updated list
    """
    if isinstance(new, dict) and new.get("type") == "override":
        return new.get("value", current)
    return add(current, new)


def add_reducer(current: list[Any], new: list[Any]) -> list[Any]:
    """Reducer that accumulates items in a list.

    Args:
        current: Current list
        new: Items to add

    Returns:
        Combined list
    """
    return add(current, new)


class DeepResearchAgentState(TypedDict, total=False):
    """Main state for the deep research agent.

    This is the entry point state that flows through the entire
    research pipeline. It contains all information needed for
    the research process.

    Attributes:
        messages: Conversation messages for context
        supervisor_messages: Messages for the supervisor subgraph
        research_brief: The research brief/question
        notes: Final compressed research notes
        raw_notes: Raw notes before compression
        final_report: The final research report
        metadata: Additional metadata
        errors: Any errors encountered
    """

    # Core messages for conversation context
    messages: Annotated[list[MessageLikeRepresentation], add_reducer]

    # Supervisor subgraph messages
    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]

    # Research brief from user
    research_brief: str

    # Final research notes (compressed)
    notes: Annotated[list[str], add_reducer]

    # Raw notes before compression
    raw_notes: Annotated[list[str], add_reducer]

    # Final report output
    final_report: str

    # Metadata for tracking
    metadata: dict[str, Any]

    # Errors encountered
    errors: list[str]


class SupervisorState(TypedDict, total=False):
    """State for the research supervisor subgraph.

    The supervisor manages research delegation to sub-researchers.
    It tracks iteration count and accumulated research notes.

    Attributes:
        supervisor_messages: Supervisor conversation messages
        research_brief: The research brief
        notes: Accumulated research notes
        research_iterations: Number of iterations completed
        raw_notes: Raw notes from research units
    """

    supervisor_messages: Annotated[list[MessageLikeRepresentation], override_reducer]
    research_brief: str
    notes: Annotated[list[str], add_reducer]
    research_iterations: int
    raw_notes: Annotated[list[str], add_reducer]


class ResearcherState(TypedDict, total=False):
    """State for individual research units.

    Each research unit operates on a specific research topic
    and maintains its own message history and tool call tracking.

    Attributes:
        research_topic: The topic this unit is researching
        researcher_messages: Conversation messages for this unit
        compressed_research: Output of compression/summarization
        tool_call_iterations: Number of tool calls made
        raw_notes: Raw notes collected during research
    """

    research_topic: str
    researcher_messages: Annotated[list[MessageLikeRepresentation], add_reducer]
    compressed_research: str
    tool_call_iterations: int
    raw_notes: Annotated[list[str], add_reducer]


class ResearcherOutputState(TypedDict, total=False):
    """Output state from individual research units.

    This is the output schema for research units, containing
    the compressed research findings.

    Attributes:
        compressed_research: Synthesized research findings
        raw_notes: Raw notes from research
    """

    compressed_research: str
    raw_notes: Annotated[list[str], add_reducer]


class ClarifyWithUser(TypedDict):
    """Structured output for user clarification requests.

    Used by the clarification node to determine if more
    information is needed from the user.

    Attributes:
        need_clarification: Whether clarification is needed
        question: Question to ask the user
        verification: Verification message if no clarification needed
    """

    need_clarification: bool
    question: str
    verification: str


class ResearchQuestion(TypedDict):
    """Structured output for research brief generation.

    Used by the brief writing node to transform user messages
    into a structured research brief.

    Attributes:
        research_brief: The generated research brief
    """

    research_brief: str


class ConductResearch(TypedDict):
    """Tool definition for conducting research.

    This is a tool that the supervisor uses to delegate
    research tasks to sub-researchers.

    Attributes:
        research_topic: The topic to research
    """

    research_topic: str


class ResearchComplete(TypedDict):
    """Tool definition indicating research is complete.

    Used by the supervisor to signal that sufficient
    research has been conducted.
    """
    pass