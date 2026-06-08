"""
Generate an interactive analytics dashboard from the JSON cache.

Panels:
  - Character network: nodes colored by community, sized by PageRank
  - Top characters by PageRank (horizontal bar)
  - Community distribution (pie)

Usage:
    python visualize.py                      # Harry Potter, up to 300 nodes
    python visualize.py --universe dune
    python visualize.py --max-nodes 150
    python visualize.py --output my_graph.html
"""
import json
import argparse
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots


CACHE_DIR = Path(__file__).parent / "cache"

COMMUNITY_COLORS = [
    '#d95f5f', '#5f8fd9', '#5fd97a', '#d9a85f',
    '#9f5fd9', '#5fd4d9', '#d97a5f', '#5fd9c0',
    '#d95fb4', '#b4d95f',
]

EDGE_COLORS: dict[str, str] = {
    "FAMILY_OF":          "#e67e22",
    "PARENT_OF":          "#e74c3c",
    "SIBLING_OF":         "#f39c12",
    "ROMANTIC_WITH":      "#e91e63",
    "MARRIED_TO":         "#e91e63",
    "FRIEND_OF":          "#2ecc71",
    "ENEMY_OF":           "#9b59b6",
    "MEMBER_OF":          "#3498db",
    "BELONGS_TO_SPECIES": "#1abc9c",
    "BELONGS_TO_RACE":    "#1abc9c",
    "FROM_HOMEWORLD":     "#00bcd4",
}


def load_cache(universe: str, max_nodes: int) -> tuple[list[dict], list[dict]]:
    cache_file = CACHE_DIR / f"{universe}.json"
    if not cache_file.exists():
        raise FileNotFoundError(
            f"Cache not found: {cache_file}\n"
            f"Run: python flows/ingest.py {universe}"
        )
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    nodes = sorted(data["nodes"], key=lambda n: n["data"]["degree"], reverse=True)[:max_nodes]
    ids = {n["data"]["id"] for n in nodes}
    edges = [e for e in data["edges"] if e["data"]["source"] in ids and e["data"]["target"] in ids]
    return nodes, edges


def compute_positions(nodes: list[dict], edges: list[dict]) -> dict[str, tuple[float, float]]:
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["data"]["id"])
    for e in edges:
        G.add_edge(e["data"]["source"], e["data"]["target"])
    k = 2.0 / len(G) ** 0.5 if len(G) > 1 else 1.0
    return nx.spring_layout(G, k=k, seed=42, iterations=60)


def _network_traces(nodes: list[dict], edges: list[dict], pos: dict) -> list[go.BaseTraceType]:
    traces: list[go.BaseTraceType] = []

    # One line-trace per relationship type so the legend shows edge categories
    rel_edges: dict[str, list] = defaultdict(list)
    for e in edges:
        rel_edges[e["data"]["rel_type"]].append(e)

    for rel_type, group in rel_edges.items():
        xs, ys = [], []
        for e in group:
            s, t = e["data"]["source"], e["data"]["target"]
            if s in pos and t in pos:
                xs += [pos[s][0], pos[t][0], None]
                ys += [pos[s][1], pos[t][1], None]
        traces.append(go.Scatter(
            x=xs, y=ys, mode='lines',
            line=dict(width=0.7, color=EDGE_COLORS.get(rel_type, "#666666")),
            hoverinfo='none',
            name=rel_type.replace("_", " ").title(),
            legendgroup=f"edge_{rel_type}",
            legendgrouptitle_text="Relationships" if rel_type == next(iter(rel_edges)) else None,
        ))

    # One marker-trace per community so the legend shows faction colors
    comm_groups: dict[int, list] = defaultdict(list)
    for n in nodes:
        comm_groups[n["data"]["community"]].append(n)

    first_comm = True
    for comm_id, group in sorted(comm_groups.items()):
        xs, ys, labels, hovers, sizes = [], [], [], [], []
        color = COMMUNITY_COLORS[comm_id % len(COMMUNITY_COLORS)]
        comm_name = group[0]["data"].get("communityName", f"Group {comm_id + 1}")

        for n in group:
            nid = n["data"]["id"]
            if nid not in pos:
                continue
            x, y = pos[nid]
            xs.append(x); ys.append(y)
            labels.append(nid if n["data"].get("rank", 9999) <= 15 else "")
            hovers.append(
                f"<b>{nid}</b><br>"
                f"Community: {comm_name}<br>"
                f"PageRank rank: #{n['data'].get('rank', '?')} / {n['data'].get('total', '?')}<br>"
                f"Connections: {n['data'].get('degree', 0)}"
            )
            sizes.append(n["data"].get("size", 12))

        traces.append(go.Scatter(
            x=xs, y=ys, mode='markers+text',
            marker=dict(size=sizes, color=color, line=dict(width=1, color='#0f0f23')),
            text=labels,
            textposition='top center',
            textfont=dict(size=9, color='#dddddd'),
            hovertext=hovers, hoverinfo='text',
            name=comm_name,
            legendgroup=f"comm_{comm_id}",
            legendgrouptitle_text="Communities" if first_comm else None,
        ))
        first_comm = False

    return traces


def _pagerank_bar(nodes: list[dict], top_n: int = 15) -> go.Bar:
    top = sorted(nodes, key=lambda n: n["data"].get("pagerank", 0), reverse=True)[:top_n]
    return go.Bar(
        x=[round(n["data"]["pagerank"] * 1000, 3) for n in top],
        y=[n["data"]["id"] for n in top],
        orientation='h',
        marker=dict(
            color=[COMMUNITY_COLORS[n["data"]["community"] % len(COMMUNITY_COLORS)] for n in top],
            line=dict(width=0.5, color='#0f0f23'),
        ),
        hovertemplate='<b>%{y}</b><br>PageRank ×1000: %{x:.3f}<extra></extra>',
        showlegend=False,
    )


def _community_pie(nodes: list[dict]) -> go.Pie:
    counts: Counter = Counter()
    names: dict[int, str] = {}
    for n in nodes:
        c = n["data"]["community"]
        counts[c] += 1
        names[c] = n["data"].get("communityName", f"Group {c + 1}")
    comm_ids = sorted(counts)
    return go.Pie(
        labels=[names[c] for c in comm_ids],
        values=[counts[c] for c in comm_ids],
        marker=dict(
            colors=[COMMUNITY_COLORS[c % len(COMMUNITY_COLORS)] for c in comm_ids],
            line=dict(width=1, color='#0f0f23'),
        ),
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>%{value} characters (%{percent})<extra></extra>',
        showlegend=False,
    )


def build_dashboard(universe: str, max_nodes: int, output: str) -> None:
    print(f"Loading cache: {universe} (up to {max_nodes} nodes)...")
    nodes, edges = load_cache(universe, max_nodes)

    print(f"Computing layout ({len(nodes)} nodes, {len(edges)} edges)...")
    pos = compute_positions(nodes, edges)

    fig = make_subplots(
        rows=2, cols=2,
        specs=[
            [{"colspan": 2, "type": "xy"}, None],
            [{"type": "xy"}, {"type": "domain"}],
        ],
        subplot_titles=(
            f"{universe.upper()} — Character Network",
            "Top Characters by PageRank",
            "Community Distribution",
        ),
        row_heights=[0.65, 0.35],
        vertical_spacing=0.08,
        horizontal_spacing=0.12,
    )

    for trace in _network_traces(nodes, edges, pos):
        fig.add_trace(trace, row=1, col=1)

    fig.add_trace(_pagerank_bar(nodes), row=2, col=1)
    fig.add_trace(_community_pie(nodes), row=2, col=2)

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0f0f23',
        plot_bgcolor='#0f0f23',
        font=dict(color='#ffffff', family='Arial'),
        height=940,
        title=dict(
            text=(
                f"<b>Fandom Knowledge Graph</b>  ·  {universe}  "
                f"<span style='font-size:13px;color:#aaaaaa'>"
                f"{len(nodes)} characters · {len(edges)} relationships</span>"
            ),
            font=dict(size=18),
            x=0.5,
        ),
        legend=dict(
            bgcolor='rgba(15,15,35,0.85)',
            bordercolor='#333',
            borderwidth=1,
            font=dict(size=11),
            groupclick='toggleitem',
        ),
        margin=dict(l=20, r=20, t=70, b=20),
    )

    # Network panel: hide axes
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False, row=1, col=1)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, row=1, col=1)

    # PageRank panel styling
    fig.update_xaxes(title_text="PageRank ×1000", showgrid=True, gridcolor='#2a2a4a', row=2, col=1)
    fig.update_yaxes(autorange="reversed", showgrid=False, row=2, col=1)

    fig.write_html(output, include_plotlyjs='cdn')
    print(f"Saved: {output}")
    print(f"Open:  file://{Path(output).resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fandom knowledge graph — analytics dashboard")
    parser.add_argument("--universe",  default="harrypotter", choices=["harrypotter", "dune"])
    parser.add_argument("--max-nodes", type=int, default=300)
    parser.add_argument("--output",    default="graph.html")
    args = parser.parse_args()
    build_dashboard(args.universe, args.max_nodes, args.output)
