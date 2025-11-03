from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

ALLOWED_TOOLS = ["query_prometheus", "query_loki"]


class ToolCall(BaseModel):
    """A single call to a tool."""

    tool_name: str = Field(
        ..., description=f"Must be one of: {ALLOWED_TOOLS}", alias="name"
    )
    tool_input: str = Field(
        ...,
        description="The query for the tool (e.g., a PromQL or LogQL query)",
        alias="query",
    )
    model_config = ConfigDict(populate_by_name=True)


class Hypothesis(BaseModel):
    """A single branch in the Tree of Thoughts."""

    hypothesis: str = Field(
        ...,
        description="The theory to investigate (e.g., 'Check the database CPU')",
        alias="description",
    )
    tools_to_call: List[ToolCall] = Field(
        ...,
        description="A list of 1 or more tool calls to test this hypothesis",
        alias="tool_calls",
    )

    evaluation_result: Optional[str] = None
    evaluation_score: Optional[int] = None
    model_config = ConfigDict(populate_by_name=True)


class OrionState(BaseModel):
    """
    The state of the agent. This is the "memory" that is passed
    between all the nodes in the graph.
    """

    initial_alert: str
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    final_conclusion: Optional[str] = None
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)


class HypothesisList(BaseModel):
    """A wrapper for a list of hypotheses for structured LLM output."""

    hypotheses: List[Hypothesis]
    model_config = ConfigDict(populate_by_name=True)
