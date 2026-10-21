from typing import Optional
from typing_extensions import TypedDict


class ResearchState(TypedDict):
    query: str
    sub_tasks: list[str]
    search_results: dict[str, list]
    analysis: str
    final_report: str
    agent_logs: list[dict]
    current_agent: str
    error: Optional[str]
    # Sub-questions that produced no usable results on the last pass. The
    # refiner rewrites these; the researcher retries only these.
    unanswered_tasks: list[str]
    # How many refine/re-search rounds have run. Bounds the retry loop.
    retry_count: int
