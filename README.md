# fandom-knowledge-graph

A knowledge graph of characters, races, and factions across fictional universes, built from Fandom wiki data.

The pipeline fetches pages via the official MediaWiki API, parses infoboxes, and builds a social network of characters — no scraping, no ban risk.

---

## How it works

```
Fandom Wiki API
     │
     ▼
┌─────────────┐     ┌──────────────┐     ┌───────────────────┐
│   Ingestion  │────▶│   Parsing    │────▶│  Graph DB         │
│  (Prefect)  │     │  (infoboxes) │     │  (Neo4j)          │
└─────────────┘     └──────────────┘     └────────┬──────────┘
                                                   │
                                                   ▼
                                         ┌──────────────────┐
                                         │  Web UI          │
                                         │  (FastAPI +      │
                                         │   Cytoscape.js)  │
                                         └──────────────────┘
```

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Orchestration | [Prefect](https://www.prefect.io/) | Modern, lightweight, runs locally with one command |
| Data source | [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page) | Official, free, no scraping needed |
| Parsing | `mwparserfromhell` | Parses wiki markup and infobox templates |
| Database | Neo4j (Docker) | Native graph DB, free community edition |
| Visualization | [FastAPI](https://fastapi.tiangolo.com/) + [Cytoscape.js](https://js.cytoscape.org/) | Live web UI — universe picker, search, click-to-explore |
| Language | Python 3.11+ | |

---

## Supported universes

- Harry Potter (`harrypotter.fandom.com`)
- Lord of the Rings (`lotr.fandom.com`)
- Dune (`dune.fandom.com`)

Adding a new universe = one block in the config file.

---

## What gets parsed from infoboxes

Example — Harry Potter's page:

```
family:      Lily Potter, James Potter
siblings:    (none)
affiliation: Gryffindor, Order of the Phoenix
species:     Human (half-blood)
```

Each field becomes a typed edge in the graph: `PARENT_OF`, `MEMBER_OF`, `BELONGS_TO_SPECIES`, etc.

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/your-repo/fandom-knowledge-graph.git
cd fandom-knowledge-graph
py -m pip install -r requirements.txt
```

### 2. Copy env config

```bash
cp .env.example .env   # credentials are already filled in for local Neo4j
```

### 3. Run the ingestion pipeline (first time only)

Requires Docker to be running.

```bash
py flows/ingest.py all               # all universes, 200 characters each
py flows/ingest.py all 500           # all universes, 500 characters each
py flows/ingest.py harrypotter 300   # single universe
```

### 4. Start the app

```bash
start.bat
```

This starts Neo4j (Docker) and the web server in one command.
Then open **http://localhost:8000**, pick a universe, and the graph loads.

To stop: `Ctrl+C` kills the web server. To also stop Neo4j: `docker compose down`.

---

## Project structure

```
fandom-knowledge-graph/
├── flows/
│   ├── __init__.py
│   ├── ingest.py          # Prefect flow: API → parse → Neo4j
│   ├── parse.py           # infobox parsing (no Prefect, independently testable)
│   └── load.py            # Neo4j write logic (no Prefect, independently testable)
├── web/
│   └── index.html         # Cytoscape.js single-page UI
├── config/
│   └── universes.yaml     # universe configs: API URL, categories, field→edge mappings
├── server.py              # FastAPI: serves the UI and /api/graph, /api/universes
├── start.bat              # single command: starts Neo4j + web server
├── requirements.txt
├── docker-compose.yml
├── .env                   # local credentials (do not commit)
└── .env.example           # template
```

---

## Example output

After running on the Harry Potter wiki, the graph contains ~500 characters and ~2 000 edges. In the browser you can:

- click a character to highlight their connections
- hover edges to see the relationship type (family / member / enemy / …)
- zoom, pan, and drag nodes freely

---
