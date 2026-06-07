"""
Web server for the fandom knowledge graph UI.

Usage:
    uvicorn server:app --reload
    # then open http://localhost:8000
"""
import json
import os
import pathlib

import requests as http_requests
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "fandom123")

_root      = pathlib.Path(__file__).parent
_cache_dir = _root / "cache"
with (_root / "config" / "universes.yaml").open() as f:
    UNIVERSES: dict = yaml.safe_load(f)

app = FastAPI(title="Fandom Knowledge Graph")


@app.get("/", response_class=HTMLResponse)
def index():
    return (_root / "web" / "index.html").read_text(encoding="utf-8")


@app.get("/api/universes")
def list_universes():
    return [{"id": k, "name": v["name"]} for k, v in UNIVERSES.items() if k != "field_aliases"]


@app.get("/api/graph")
def get_graph(
    universe: str = Query("harrypotter"),
    max_nodes: int = Query(300, ge=10, le=2000),
):
    # ── Cache path (written by ingest.py) ──
    cache_file = _cache_dir / f"{universe}.json"
    if cache_file.exists():
        data  = json.loads(cache_file.read_text(encoding="utf-8"))
        nodes = sorted(data["nodes"], key=lambda n: n["data"]["degree"], reverse=True)[:max_nodes]
        ids   = {n["data"]["id"] for n in nodes}
        edges = [e for e in data["edges"] if e["data"]["source"] in ids and e["data"]["target"] in ids]
        return {"nodes": nodes, "edges": edges}

    # ── Fallback: live Neo4j query (local dev without cache) ──
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            node_rows = session.run(
                """
                MATCH (c:Character {universe: $u})
                OPTIONAL MATCH (c)-[r]-()
                RETURN c.name AS name, count(r) AS degree
                ORDER BY degree DESC
                LIMIT $limit
                """,
                u=universe, limit=max_nodes,
            ).data()

            if not node_rows:
                return {"nodes": [], "edges": []}

            names      = [r["name"] for r in node_rows]
            max_degree = max(r["degree"] for r in node_rows) or 1

            nodes = [
                {
                    "data": {
                        "id":     r["name"],
                        "label":  r["name"],
                        "degree": r["degree"],
                        "size":   10 + int(30 * r["degree"] / max_degree),
                    }
                }
                for r in node_rows
            ]

            edge_rows = session.run(
                """
                MATCH (a:Character {universe: $u})-[r]->(b:Character {universe: $u})
                WHERE a.name IN $names AND b.name IN $names
                RETURN a.name AS source, type(r) AS rel_type, b.name AS target
                LIMIT 3000
                """,
                u=universe, names=names,
            ).data()

            edges = [
                {
                    "data": {
                        "source":   r["source"],
                        "target":   r["target"],
                        "rel_type": r["rel_type"],
                        "label":    r["rel_type"].replace("_", " ").title(),
                    }
                }
                for r in edge_rows
            ]
    finally:
        driver.close()

    return {"nodes": nodes, "edges": edges}


_WIKI_HEADERS = {"User-Agent": "fandom-knowledge-graph/1.0 (educational project)"}


@app.get("/api/character")
def get_character(universe: str = Query("harrypotter"), name: str = Query(...)):
    config = UNIVERSES.get(universe)
    if not config:
        return {"summary": ""}
    try:
        resp = http_requests.get(
            config["api_url"],
            params={
                "action": "query",
                "titles": name,
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "exsentences": 3,
                "format": "json",
            },
            headers=_WIKI_HEADERS,
            timeout=10,
        )
        pages = resp.json().get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        return {"summary": page.get("extract", "").strip()}
    except Exception:
        return {"summary": ""}
