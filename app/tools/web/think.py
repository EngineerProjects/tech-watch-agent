"""
Think tool for agent reflection and strategic planning.

The ThinkTool implements the "think" phase of the ReAct pattern (Reasoning + Acting).
It helps agents reflect on their current state, plan next steps, and stay rational
by forcing deliberate thinking before taking actions.

This is especially valuable in multi-agent systems where:
- The supervisor needs to plan before delegating
- Researchers need to assess what they've found before searching more
- The orchestrator needs to evaluate progress before continuing

Unlike search/crawl tools that gather external information, ThinkTool
operates purely on the agent's internal state and reasoning.
"""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class ThinkTool(BaseTool):
    """Reflection and strategic planning tool for AI agents.

    Provides a structured way for agents to think through:
    - What they've learned so far
    - What information is still missing
    - What action to take next
    - Potential issues with their approach

    The tool accepts a thinking context and returns a structured
    reflection that helps the agent make better decisions.

    Attributes:
        model: Model to use for thinking (default: uses same as agent)
        max_thinking_tokens: Maximum tokens for thinking output
    """

    def __init__(
        self,
        max_thinking_tokens: int = 1500,
    ) -> None:
        super().__init__()
        self._max_thinking_tokens = max_thinking_tokens

    @property
    def name(self) -> str:
        return "think_tool"

    @property
    def description(self) -> str:
        return """Strategic thinking and reflection tool for AI agents.

Use this tool to think through complex decisions before taking action.
It helps you:

1. ASSESS what you've learned so far
2. IDENTIFY what information is still missing
3. PLAN your next specific action
4. CATCH issues with your current approach

ThinkTool is NOT for gathering external information - use web search
tools for that. ThinkTool is purely for internal reasoning and planning.

Best used:
- Before making important decisions
- After receiving new information (to process it)
- When unsure about next steps
- To catch contradictions or gaps in reasoning

The thinking context you provide should include:
- Current task/goal
- What you've learned or done so far
- What you're uncertain about
- What options you're considering

Returns a structured reflection with: key_insights, gaps, recommended_action, confidence.
"""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Your current context, observations, or decision to think through. Include: current goal, what you've learned, what you're uncertain about, what options you're considering.",
                },
                "depth": {
                    "type": "string",
                    "description": "Depth of thinking: 'quick' (1-2 sentences), 'standard' (paragraph), 'deep' (detailed analysis)",
                    "enum": ["quick", "standard", "deep"],
                    "default": "standard",
                },
            },
            "required": ["input"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        thinking_context = params.get("input", "")
        depth = params.get("depth", "standard")

        if not thinking_context:
            return {
                "success": False,
                "data": None,
                "error": "No thinking context provided",
                "metadata": {},
            }

        max_tokens_map = {
            "quick": 300,
            "standard": 800,
            "deep": 2000,
        }
        max_tokens = max_tokens_map.get(depth, 800)

        from app.services.llm import ChatCompletionClient
        try:
            client = ChatCompletionClient()
        except Exception as exc:
            logger.warning("Could not create LLM client for ThinkTool: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": "LLM not configured for ThinkTool",
                "metadata": {},
            }

        prompt = f"""You are a strategic thinking assistant. Think carefully and precisely about the following:

{thinking_context}

Think through this systematically:
1. What key insights or conclusions can you draw from what you've learned?
2. What information or understanding is still missing or unclear?
3. What specific action would be most valuable next?
4. Are there any issues, contradictions, or risks with your current approach?
5. How confident are you in your current understanding? (high/medium/low)

Be honest about uncertainty. Focus on what's most actionable."""

        try:
            response = client.generate_completion(
                prompt=prompt,
                system_message="You are a precise, honest strategic thinking assistant. You think carefully before responding.",
                temperature=0.3,
                max_tokens=max_tokens,
            )

            reflection = self._parse_reflection(response)

            logger.debug("ThinkTool completed: depth=%s, confidence=%s", depth, reflection.get("confidence", "unknown"))

            return {
                "success": True,
                "data": reflection,
                "error": None,
                "metadata": {
                    "depth": depth,
                    "input_length": len(thinking_context),
                    "output_length": len(response),
                },
            }

        except Exception as exc:
            logger.error("ThinkTool failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    @staticmethod
    def _parse_reflection(response: str) -> dict[str, Any]:
        """Parse LLM response into structured reflection.

        Tries to extract key fields from the response.
        If parsing fails, returns the raw response in a structured format.
        """
        import re

        lines = response.strip().split("\n")
        result = {
            "raw_thinking": response,
            "key_insights": [],
            "gaps": [],
            "recommended_action": "",
            "confidence": "medium",
            "concerns": [],
        }

        current_section = None
        for line in lines:
            line_clean = line.strip().strip("-*").strip()
            line_lower = line_clean.lower()

            if any(x in line_lower for x in ["key insight", "insights:", "what i learned", "conclusions"]):
                current_section = "insights"
            elif any(x in line_lower for x in ["missing", "gaps:", "unclear", "don't know"]):
                current_section = "gaps"
            elif any(x in line_lower for x in ["action:", "next step", "recommend", "should"]):
                current_section = "action"
            elif any(x in line_lower for x in ["confidence:", "confident:", "certainty"]):
                current_section = "confidence"
            elif any(x in line_lower for x in ["concern", "issue", "risk", "problem", "contradiction"]):
                current_section = "concerns"
            else:
                if current_section == "insights" and line_clean:
                    result["key_insights"].append(line_clean)
                elif current_section == "gaps" and line_clean:
                    result["gaps"].append(line_clean)
                elif current_section == "action" and line_clean:
                    result["recommended_action"] += " " + line_clean
                elif current_section == "concerns" and line_clean:
                    result["concerns"].append(line_clean)

        confidence_match = re.search(r"(high|medium|low)", response.lower())
        if confidence_match:
            result["confidence"] = confidence_match.group(1)

        if not result["recommended_action"]:
            result["recommended_action"] = response.strip()[:200]

        return result

    async def execute_safe(self, params: dict[str, Any]) -> dict[str, Any]:
        """Safe wrapper that catches errors."""
        try:
            return await self.execute(params)
        except Exception as exc:
            logger.error("ThinkTool execute_safe error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }