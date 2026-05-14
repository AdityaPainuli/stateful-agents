from __future__ import annotations

from ..engine import AgentEngine
from ..llm import ask_llm
from ..state import AgentState
from ..stores.base import StateStore


def build_research_agent(store: StateStore) -> AgentEngine:
    agent = AgentEngine(store)

    @agent.step("GENERATE_QUESTIONS")
    async def generate_questions(state: AgentState) -> AgentState:
        topic = state.payload["topic"]
        questions = await ask_llm(
            f"You are a research assistant.\n"
            f"Generate 5 deep research questions about:\n\"{topic}\""
        )
        state.payload["questions"] = questions
        state.step = "GENERATE_PLAN"
        return state

    @agent.step("GENERATE_PLAN")
    async def generate_plan(state: AgentState) -> AgentState:
        questions = state.payload["questions"]
        plan = await ask_llm(
            f"Based on these research questions:\n{questions}\n\n"
            "Create a structured 5-part research plan, one part per line."
        )
        state.payload["plan"] = plan
        state.step = "FETCH_DATA"
        return state

    @agent.step("FETCH_DATA")
    async def fetch_data(state: AgentState) -> AgentState:
        plan: str = state.payload["plan"]
        plan_parts = [p.strip() for p in plan.splitlines() if p.strip()]
        index = state.payload.get("fetch_index", 0)
        state.payload.setdefault("data", [])

        part = plan_parts[index]
        data = await ask_llm(
            f"Find factual information about:\n\"{part}\"\n"
            "Cite sources and give summaries."
        )
        state.payload["data"].append({"plan_section": part, "research": data})

        index += 1
        state.payload["fetch_index"] = index
        if index >= len(plan_parts):
            state.step = "GENERATE_REPORT"
        return state

    @agent.step("GENERATE_REPORT")
    async def generate_report(state: AgentState) -> AgentState:
        report = await ask_llm(
            "Create a full research report combining the questions, plan, and data "
            "below. Format it professionally with sections.\n\n"
            f"QUESTIONS:\n{state.payload['questions']}\n\n"
            f"PLAN:\n{state.payload['plan']}\n\n"
            f"DATA:\n{state.payload['data']}"
        )
        state.payload["report"] = report
        state.step = "DONE"
        return state

    return agent
