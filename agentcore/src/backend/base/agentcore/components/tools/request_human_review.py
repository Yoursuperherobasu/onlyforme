"""RequestHumanReview tool — AI-decided Human-in-the-Loop trigger.

When an Agent's LLM decides it needs human input (Pattern 3 — AI-decided HITL),
it calls this tool.  The tool internally calls LangGraph's interrupt(), pausing
the graph exactly as if a HumanApproval node had been placed in the flow.

Pattern 3 usage:
    1. Add this tool to an Agent node's Tools input.
    2. Give the agent a system prompt that tells it when to call the tool
       (e.g. "If you are unsure or the task involves irreversible actions,
        call the request_human_review tool before proceeding.").
    3. When the agent decides to call the tool, the graph pauses.
    4. The human reviews via GET /api/v1/hitl/pending and resumes via
       POST /api/v1/hitl/{thread_id}/resume.
    5. The agent receives the human decision as the tool result and continues.
"""

from __future__ import annotations

from typing import Optional, Type

from langchain_core.tools import BaseTool, ToolException
from langgraph.types import interrupt
from loguru import logger
from pydantic import BaseModel, Field

from agentcore.base.langchain_utilities.model import LCToolNode
from agentcore.field_typing import Tool
from agentcore.inputs.inputs import MessageTextInput, MultilineInput


class RequestHumanReviewInput(BaseModel):
    """Input schema for the RequestHumanReview tool."""

    question: str = Field(
        description="What should the human reviewer be asked? State clearly what decision or input is needed."
    )
    context: Optional[str] = Field(
        default=None,
        description="The relevant context the reviewer should see (e.g. content to be approved, "
        "data being processed, or the agent's reasoning).",
    )
    actions: Optional[list[str]] = Field(
        default=None,
        description="List of action options for the reviewer (e.g. ['Approve', 'Reject', 'Edit']). "
        "If omitted, defaults to ['Approve', 'Reject'].",
    )


class _RequestHumanReviewTool(BaseTool):
    """Internal LangChain tool implementation that calls interrupt()."""

    name: str = "request_human_review"
    description: str = (
        "Request human review and approval before proceeding. "
        "Use this tool when you are uncertain, when an action is irreversible, "
        "or when business rules require human sign-off. "
        "The workflow will pause until a human reviewer responds."
    )
    args_schema: Type[BaseModel] = RequestHumanReviewInput

    def _run(self, question: str, context: str | None = None, actions: list[str] | None = None) -> str:
        """Synchronous run — not used directly (agent calls _arun)."""
        return self._invoke_interrupt(question, context, actions)

    async def _arun(
        self, question: str, context: str | None = None, actions: list[str] | None = None
    ) -> str:
        """Async run — called by the agent during tool execution.

        Calls interrupt() which pauses the LangGraph execution.  After the
        human resumes the run, interrupt() returns the human's decision and
        this method returns it as a string to the agent.
        """
        return self._invoke_interrupt(question, context, actions)

    def _invoke_interrupt(
        self,
        question: str,
        context: str | None,
        actions: list[str] | None,
    ) -> str:
        effective_actions = actions or ["Approve", "Reject"]
        logger.info(
            f"[RequestHumanReview] Agent requesting human review. "
            f"question={question!r}, actions={effective_actions}"
        )
        human_decision: dict = interrupt(
            {
                "question": question,
                "context": context or "",
                "actions": effective_actions,
                "source": "agent_tool",  # differentiates from HumanApproval node
            }
        )
        # Format the decision for the agent to understand.
        if isinstance(human_decision, dict):
            action = human_decision.get("action", effective_actions[0])
            feedback = human_decision.get("feedback", "")
            parts = [f"Human decision: {action}"]
            if feedback:
                parts.append(f"Feedback: {feedback}")
            return "\n".join(parts)
        return str(human_decision)


class RequestHumanReviewComponent(LCToolNode):
    """Agent tool that pauses workflow execution and requests human review.

    Place this in an Agent's Tools input.  When the agent's LLM decides
    human input is needed, it calls this tool and the graph pauses.

    This implements Pattern 3 (AI-decided) HITL:
      - The LLM autonomously decides when human review is needed.
      - No fixed node placement required — the agent decides dynamically.
      - Use with a system prompt that explains when to call this tool.
    """

    display_name = "Request Human Review (Tool)"
    description = (
        "Give your Agent the ability to request human approval at any point. "
        "When the agent calls this tool, the workflow pauses until a human responds. "
        "Best used with a system prompt that tells the agent when to request review."
    )
    icon = "UserCheck"
    name = "RequestHumanReview"
    beta = False

    inputs = [
        MultilineInput(
            name="tool_description",
            display_name="Tool Description",
            info=(
                "How the agent should understand when to use this tool. "
                "This description is shown to the LLM."
            ),
            value=(
                "Request human review and approval before proceeding. "
                "Use this when you are uncertain about the correct action, "
                "when an operation is irreversible, or when business rules require human sign-off."
            ),
            advanced=True,
        ),
        MessageTextInput(
            name="default_actions",
            display_name="Default Actions",
            info="Comma-separated list of default action options when the agent doesn't specify any "
            "(e.g. 'Approve, Reject, Provide More Info'). Agent can override these per call.",
            value="Approve, Reject",
            advanced=True,
        ),
    ]

    def build_tool(self) -> Tool:
        """Return the LangChain tool the agent will call."""
        tool = _RequestHumanReviewTool()
        # Override description with the user's customised text.
        if self.tool_description:
            tool.description = self.tool_description
        return tool

    def run_model(self):
        """Not used — agents access the tool directly via build_tool()."""
        return []
