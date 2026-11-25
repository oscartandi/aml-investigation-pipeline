from typing import Optional
import networkx as nx
from app.schemas import NetworkEdge, StageResult


def run_network_stage(
    entity_id: str,
    edges: list[NetworkEdge],
    known_high_risk_nodes: Optional[list[str]] = None,
    max_hops: int = 3,
) -> StageResult:
    """Analyze multi-hop links to high-risk nodes, UBO/device ties, and circular flows."""
    high_risk_set = set(known_high_risk_nodes or [])

    if not edges:
        return StageResult(
            stage="network_forensics",
            score=0.0,
            flagged=False,
            reasons=["No network graph edges supplied for entity"],
            metadata={"node_count": 1 if entity_id else 0, "edge_count": 0},
        )

    graph = nx.DiGraph()
    for edge in edges:
        graph.add_edge(edge.source, edge.target, relation=edge.relation, weight=edge.weight)

    score = 0.0
    reasons: list[str] = []
    shortest_hr_path: Optional[list[str]] = None

    # 1. Shortest path to any known high-risk node within max_hops (undirected reachability
    #    captures both outgoing transfers and shared ownership/device links)
    undirected = graph.to_undirected()
    if entity_id in undirected:
        for hr_node in high_risk_set:
            if hr_node == entity_id:
                score += 60.0
                reasons.append(f"Entity '{entity_id}' is directly listed as a high-risk node")
                shortest_hr_path = [entity_id]
                break
            if hr_node in undirected and nx.has_path(undirected, entity_id, hr_node):
                path = nx.shortest_path(undirected, entity_id, hr_node)
                hops = len(path) - 1
                if hops <= max_hops:
                    hop_penalty = {1: 45.0, 2: 30.0, 3: 18.0}.get(hops, 10.0)
                    score += hop_penalty
                    shortest_hr_path = path
                    reasons.append(
                        f"{hops}-hop link to high-risk node '{hr_node}' via path: {' -> '.join(path)}"
                    )

                    # Inspect edge relations along the path for UBO or shared-device mule signals
                    for u, v in zip(path[:-1], path[1:]):
                        edge_data = (
                            graph.get_edge_data(u, v)
                            or graph.get_edge_data(v, u)
                            or {}
                        )
                        rel = edge_data.get("relation", "")
                        if rel == "BENEFICIAL_OWNER":
                            score += 15.0
                            reasons.append(f"Hidden UBO / ownership tie detected on link ({u} <-> {v})")
                        elif rel == "SHARED_DEVICE":
                            score += 15.0
                            reasons.append(f"Shared device / mule infrastructure link ({u} <-> {v})")

    # 2. Detect circular money flow / cycles involving the entity
    cycles_involving_entity = []
    if entity_id in graph:
        for cycle in nx.simple_cycles(graph):
            if entity_id in cycle and len(cycle) >= 2:
                cycles_involving_entity.append(cycle)

    if cycles_involving_entity:
        score += 25.0
        sample_cycle = " -> ".join(cycles_involving_entity[0] + [cycles_involving_entity[0][0]])
        reasons.append(
            f"Circular flow detected ({len(cycles_involving_entity)} cycle(s)); sample: {sample_cycle}"
        )

    clamped_score = round(min(100.0, score), 2)
    flagged = clamped_score >= 25.0

    if not reasons:
        reasons.append("No high-risk multi-hop paths or circular flows detected within threshold")

    return StageResult(
        stage="network_forensics",
        score=clamped_score,
        flagged=flagged,
        reasons=reasons,
        metadata={
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "shortest_high_risk_path": shortest_hr_path,
            "circular_flow_count": len(cycles_involving_entity),
        },
    )