from langgraph.graph import StateGraph, END
from state.graph_state import GraphState
from agents.resume_parser_agent import resume_parser_agent
from agents.ats_scorer_agent import ats_scorer_agent
from agents.candidate_search_agent import candidate_search_agent
from agents.report_generator_agent import report_generator_agent


def router_node(state: GraphState) -> str:
    """Conditional edge: routes to the correct agent based on state['route']."""
    return state.get("route", "upload")


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    # Register agent nodes
    graph.add_node("resume_parser_agent",    resume_parser_agent)
    graph.add_node("ats_scorer_agent",       ats_scorer_agent)
    graph.add_node("candidate_search_agent", candidate_search_agent)
    graph.add_node("report_generator_agent", report_generator_agent)

    # Conditional routing from START
    graph.set_conditional_entry_point(
        router_node,
        {
            "upload": "resume_parser_agent",
            "score":  "ats_scorer_agent",
            "search": "candidate_search_agent",
        }
    )

    # Linear edge: search always followed by report generation
    graph.add_edge("candidate_search_agent", "report_generator_agent")

    # Terminal edges
    graph.add_edge("resume_parser_agent",    END)
    graph.add_edge("ats_scorer_agent",       END)
    graph.add_edge("report_generator_agent", END)

    return graph.compile()


# Singleton compiled graph
ats_graph = build_graph()


def run_graph(initial_state: dict) -> GraphState:
    """Execute the ATS graph with the given initial state."""
    result = ats_graph.invoke(initial_state)
    return result
