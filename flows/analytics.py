"""
Graph analytics: PageRank + Louvain community detection.
Enriches the node list in-place; results are embedded in the JSON cache.
"""
from __future__ import annotations

import networkx as nx


def _pagerank(G: nx.DiGraph, alpha: float = 0.85, max_iter: int = 100, tol: float = 1e-6) -> dict:
    """Pure-Python power-iteration PageRank — no scipy/numpy needed."""
    N = len(G)
    if N == 0:
        return {}
    nodes = list(G.nodes())
    rank  = {n: 1.0 / N for n in nodes}
    dangling = [n for n in nodes if G.out_degree(n) == 0]

    for _ in range(max_iter):
        prev = rank.copy()
        dangling_sum = alpha / N * sum(prev[n] for n in dangling)
        for n in nodes:
            in_contrib = sum(
                prev[nbr] / G.out_degree(nbr)
                for nbr in G.predecessors(n)
                if G.out_degree(nbr) > 0
            )
            rank[n] = alpha * in_contrib + dangling_sum + (1.0 - alpha) / N
        if sum(abs(rank[n] - prev[n]) for n in nodes) < N * tol:
            break
    return rank

COMMUNITY_COLORS = [
    '#d95f5f',  # red
    '#5f8fd9',  # blue
    '#5fd97a',  # green
    '#d9a85f',  # amber
    '#9f5fd9',  # purple
    '#5fd4d9',  # cyan
    '#d97a5f',  # coral
    '#5fd9c0',  # teal
    '#d95fb4',  # pink
    '#b4d95f',  # lime
]


def compute_analytics(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """
    Enrich node dicts with pagerank, rank, community, communityColor, and size.
    Mutates and returns the same list.
    """
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["data"]["id"])
    for e in edges:
        G.add_edge(
            e["data"]["source"],
            e["data"]["target"],
            rel_type=e["data"]["rel_type"],
        )

    pagerank = _pagerank(G, alpha=0.85)

    # Community detection on undirected projection with fixed seed for reproducibility
    G_u = G.to_undirected()
    communities = list(nx.community.louvain_communities(G_u, seed=42))
    community_map: dict[str, int] = {}
    for idx, members in enumerate(communities):
        for node_id in members:
            community_map[node_id] = idx

    max_pr = max(pagerank.values()) if pagerank else 1.0
    total  = len(nodes)

    sorted_ids = sorted(pagerank, key=lambda k: pagerank[k], reverse=True)
    rank_map   = {nid: i + 1 for i, nid in enumerate(sorted_ids)}

    for node in nodes:
        nid  = node["data"]["id"]
        pr   = pagerank.get(nid, 0.0)
        comm = community_map.get(nid, 0)
        node["data"]["pagerank"]       = round(pr, 6)
        node["data"]["rank"]           = rank_map.get(nid, total)
        node["data"]["total"]          = total
        node["data"]["community"]      = comm
        node["data"]["communityColor"] = COMMUNITY_COLORS[comm % len(COMMUNITY_COLORS)]
        node["data"]["size"]           = 12 + int(28 * pr / max_pr)

    return nodes
