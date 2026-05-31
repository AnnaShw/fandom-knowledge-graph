"""
Generate an interactive HTML graph from Neo4j data.

Usage:
    python visualize.py                          # Harry Potter, up to 300 nodes
    python visualize.py --universe lotr          # Lord of the Rings
    python visualize.py --max-nodes 100          # smaller graph, faster layout
    python visualize.py --output my_graph.html
"""
import os
import argparse
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pyvis.network import Network

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "fandom123")

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

PYVIS_OPTIONS = """
{
  "physics": {
    "solver": "forceAtlas2Based",
    "forceAtlas2Based": {
      "gravitationalConstant": -60,
      "centralGravity": 0.005,
      "springLength": 130,
      "springConstant": 0.05,
      "damping": 0.4
    },
    "stabilization": {"iterations": 200, "fit": true}
  },
  "nodes": {
    "shape": "dot",
    "size": 16,
    "borderWidth": 2,
    "borderWidthSelected": 4,
    "font": {"size": 14, "face": "Arial", "color": "#ffffff"}
  },
  "edges": {
    "arrows": {"to": {"enabled": true, "scaleFactor": 0.6}},
    "smooth": {"type": "curvedCW", "roundness": 0.2},
    "width": 1.5
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 150,
    "navigationButtons": true,
    "keyboard": true
  }
}
"""


def build_graph(universe: str, max_nodes: int = 300, output: str = "graph.html") -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    net = Network(
        height="95vh",
        width="100%",
        bgcolor="#0f0f23",
        font_color="#ffffff",
        directed=True,
        notebook=False,
    )
    net.set_options(PYVIS_OPTIONS)

    with driver.session() as session:
        # Prioritize well-connected characters so the graph is interesting at any size limit
        node_records = session.run(
            """
            MATCH (c:Character {universe: $u})
            OPTIONAL MATCH (c)-[r]-()
            RETURN c.name AS name, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            """,
            u=universe, limit=max_nodes,
        ).data()

        if not node_records:
            print(f"No characters found for universe '{universe}'. Did you run the ingestion?")
            driver.close()
            return

        node_names = [r["name"] for r in node_records]
        max_degree = max(r["degree"] for r in node_records) or 1

        for r in node_records:
            size = 10 + int(30 * (r["degree"] / max_degree))
            net.add_node(r["name"], label=r["name"], title=r["name"], size=size)

        edge_records = session.run(
            """
            MATCH (a:Character {universe: $u})-[r]->(b:Character {universe: $u})
            WHERE a.name IN $names AND b.name IN $names
            RETURN a.name AS source, type(r) AS rel_type, b.name AS target
            LIMIT 3000
            """,
            u=universe, names=node_names,
        ).data()

        for r in edge_records:
            color = EDGE_COLORS.get(r["rel_type"], "#888888")
            label = r["rel_type"].replace("_", " ").title()
            net.add_edge(r["source"], r["target"], title=label, color=color)

    driver.close()

    net.save_graph(output)
    abs_path = os.path.abspath(output)
    print(f"Saved: {output}  ({len(net.nodes)} nodes, {len(net.edges)} edges)")
    print(f"Open:  file://{abs_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize the fandom knowledge graph")
    parser.add_argument("--universe",  default="harrypotter")
    parser.add_argument("--max-nodes", type=int, default=300)
    parser.add_argument("--output",    default="graph.html")
    args = parser.parse_args()
    build_graph(args.universe, args.max_nodes, args.output)
