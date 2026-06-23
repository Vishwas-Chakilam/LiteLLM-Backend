from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents import get_agent_instance
from app.orchestrator.manager import ManagerAgent

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    query: str
    conversation_id: str | None
    patient_context: dict[str, Any]
    intent: str
    urgency: str
    selected_agents: list[str]
    agent_outputs: dict[str, Any]
    emergency: bool
    final_output: str
    agents_used: list[str]


def _classify_node(state: GraphState) -> GraphState:
    manager = ManagerAgent()
    intent_data = manager.classify_intent(state["query"])
    agents = manager.select_agents(state["query"], intent_data)
    return {
        **state,
        "intent": intent_data.get("intent", "general"),
        "urgency": intent_data.get("urgency", "routine"),
        "emergency": intent_data.get("urgency") == "emergency",
        "selected_agents": agents,
        "agent_outputs": {},
        "agents_used": [],
    }


async def _execute_agents_node(state: GraphState) -> GraphState:
    outputs = dict(state.get("agent_outputs", {}))
    used = list(state.get("agents_used", []))
    ctx = state.get("patient_context", {})
    conv_id = state.get("conversation_id")

    for agent_id in state.get("selected_agents", []):
        if agent_id == "compliance_safety_agent":
            continue
        instance = get_agent_instance(agent_id)
        if not instance:
            continue
        try:
            output = await instance.run({"query": state["query"], **ctx}, conv_id)
            outputs[agent_id] = output
            used.append(agent_id)
            if output.get("emergency"):
                state = {**state, "emergency": True}
        except Exception as exc:
            outputs[agent_id] = {"error": str(exc)}

    return {**state, "agent_outputs": outputs, "agents_used": used}


async def _safety_node(state: GraphState) -> GraphState:
    safety = get_agent_instance("compliance_safety_agent")
    if safety:
        result = await safety.run(
            {
                "query": state["query"],
                "content": str(state.get("agent_outputs", {})),
                "agent_outputs": state.get("agent_outputs", {}),
                "emergency": state.get("emergency", False),
            },
            state.get("conversation_id"),
        )
        outputs = dict(state.get("agent_outputs", {}))
        outputs["compliance_safety_agent"] = result
        used = list(state.get("agents_used", []))
        used.append("compliance_safety_agent")
        return {**state, "agent_outputs": outputs, "agents_used": used}
    return state


def _synthesize_node(state: GraphState) -> GraphState:
    manager = ManagerAgent()
    final = manager._synthesize(state)  # noqa: SLF001
    return {**state, "final_output": final}


def build_healthcare_graph():
    """LangGraph workflow: classify → execute agents → safety → synthesize."""
    graph = StateGraph(GraphState)
    graph.add_node("classify", _classify_node)
    graph.add_node("execute_agents", _execute_agents_node)
    graph.add_node("safety", _safety_node)
    graph.add_node("synthesize", _synthesize_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "execute_agents")
    graph.add_edge("execute_agents", "safety")
    graph.add_edge("safety", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


async def run_langgraph_workflow(
    query: str,
    conversation_id: str | None = None,
    patient_context: dict[str, Any] | None = None,
) -> GraphState:
    app = build_healthcare_graph()
    initial: GraphState = {
        "query": query,
        "conversation_id": conversation_id,
        "patient_context": patient_context or {},
    }
    return await app.ainvoke(initial)
