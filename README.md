# fandom-knowledge-graph

A knowledge graph of characters and their relationships across fictional universes, built from Fandom wiki data.

The pipeline fetches pages via the official MediaWiki API, parses infoboxes, and builds a social network of characters — no scraping, no ban risk.

---

## How it works

```
Fandom Wiki API
     │  batch fetch (50 pages/request)
     ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│  Ingestion  │────▶│   Parsing    │────▶│  JSON cache  │────▶│  Web UI           │
│  (Prefect)  │     │  (infoboxes) │     │  cache/*.json│     │  (FastAPI +       │
└─────────────┘     └──────────────┘     └──────────────┘     │   Cytoscape.js)   │
       │                                                        └───────────────────┘
       ▼ optional
┌───────────────┐
│  Neo4j        │
│  (Docker)     │
└───────────────┘
```

The server always reads from the JSON cache first. Neo4j is only needed if you want to re-ingest locally.

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Orchestration | [Prefect](https://www.prefect.io/) | Modern, lightweight, runs locally with one command |
| Data source | [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page) | Official, free, no scraping needed |
| Parsing | `mwparserfromhell` | Parses wiki markup and infobox templates |
| Cache | JSON files (`cache/*.json`) | Zero-dependency serving; refreshed by CI; includes analytics |
| Database | Neo4j (Docker) | Optional — used during local re-ingestion only |
| Analytics | [NetworkX](https://networkx.org/) | PageRank + Louvain community detection |
| Web server | [FastAPI](https://fastapi.tiangolo.com/) | Serves the UI and REST endpoints |
| Visualization | [Cytoscape.js](https://js.cytoscape.org/) | Interactive graph — pan, zoom, click, search, path finder |
| CI refresh | GitHub Actions | Runs ingestion weekly, commits updated cache |
| Language | Python 3.12+ | |

---

## Supported universes

| Universe | Wiki | Method |
|---|---|---|
| Harry Potter | `harrypotter.fandom.com` | Template: `Individual infobox` |
| Lord of the Rings | `lotr.fandom.com` | Category: `The Lord of the Rings characters` |
| Dune | `dune.fandom.com` | Category: `Characters` |

Adding a new universe = one block in `config/universes.yaml`. No code changes needed.

---

## Field aliases (dynamic, global)

Instead of hardcoding field names per universe, `universes.yaml` defines global aliases that map any wiki field name to a relationship type:

```yaml
field_aliases:
  FAMILY_OF:     [family, parentage, relatives, kin]
  PARENT_OF:     [parents, children, offspring, sons, daughters]
  SIBLING_OF:    [siblings, brothers, sisters]
  MARRIED_TO:    [spouse, spouses, wife, husband, consort]
  ROMANTIC_WITH: [romances, romance, partner, lover]
  MEMBER_OF:     [affiliation, house, culture, loyalty, allegiance, ...]
  FRIEND_OF:     [friends, allies, companions]
  ENEMY_OF:      [enemies, rivals, nemesis]
  ...
```

Each infobox field found on any wiki is automatically mapped to the right edge type. New field names just need an entry here.

---

## Quick start

### Option A — Use the pre-built cache (no Docker, no ingestion)

The `cache/` folder is committed to the repo and refreshed automatically by CI every week.

```bash
git clone https://github.com/your-repo/fandom-knowledge-graph.git
cd fandom-knowledge-graph
py -m pip install -r requirements.txt
py -m uvicorn server:app --reload
```

Open **http://localhost:8000**, pick a universe — done.

---

### Option B — Re-ingest locally (requires Docker)

```bash
# 1. Install
py -m pip install -r requirements.txt

# 2. Start Neo4j
docker compose up -d

# 3. Ingest
py flows/ingest.py all 300 --clear        # all universes, wipe stale data first
py flows/ingest.py harrypotter 500        # single universe
py flows/ingest.py lotr 200 --clear       # single universe, clear first

# 4. Start the app
start.bat     # starts Neo4j + web server in one command
```

The `--clear` flag deletes existing data for that universe before re-ingesting.  
The `--cache-only` flag skips Neo4j entirely and only writes the JSON cache (used by CI).

---

## Automatic cache refresh (GitHub Actions)

The workflow in `.github/workflows/refresh-cache.yml` runs every Monday at 03:00 UTC:

1. Fetches fresh data from all wiki APIs
2. Writes updated `cache/*.json`
3. Commits and pushes the changes

You can also trigger it manually from the **Actions** tab.

---

## Graph analytics

After each ingestion run, the following metrics are computed and embedded in the JSON cache:

| Metric | Algorithm | Effect in UI |
|---|---|---|
| **PageRank** | Power-iteration  | Node size — narratively important characters appear larger even with few direct links |
| **Community detection** | Louvain (via NetworkX) | Node color — auto-discovered factions/houses get distinct colors |
| **Rank** | Sorted by PageRank | Shown in info panel: "Rank #3 of 300" |

---

## UI features

- Universe picker — auto-loads graph on selection
- Max-nodes slider — show top N characters by connection count (ranked by PageRank)
- Search box — highlights matching nodes and their neighbours
- Click a node — info panel shows wiki bio, rank, community group, all relationships
- Click an edge — shows the relationship between two characters
- **Path finder** — after clicking a character, type another name and press Enter to find the shortest connection path; highlighted in gold with hop-by-hop relationship labels
- Clickable legend — filter by relationship type (left side) or community group (right side)
- Click background — clears all highlights

---

## Project structure

```
fandom-knowledge-graph/
├── flows/
│   ├── ingest.py          # Prefect flow: API → parse → Neo4j + JSON cache
│   ├── parse.py           # infobox parsing (no Prefect, independently testable)
│   ├── load.py            # Neo4j write logic (no Prefect, independently testable)
│   └── analytics.py       # PageRank + Louvain community detection (pure Python)
├── web/
│   └── index.html         # Cytoscape.js single-page UI
├── cache/
│   ├── harrypotter.json   # pre-built graph data (committed to repo)
│   ├── lotr.json
│   └── dune.json
├── config/
│   └── universes.yaml     # universe configs + global field aliases
├── .github/
│   └── workflows/
│       └── refresh-cache.yml  # weekly CI job
├── server.py              # FastAPI: serves UI + /api/graph, /api/universes, /api/character
├── start.bat              # starts Neo4j + web server in one command
├── docker-compose.yml
├── requirements.txt
├── .env                   # local credentials (do not commit)
└── .env.example
```

---

## Ingestion performance

| Metric | Before | After |
|---|---|---|
| HTTP requests per 200 chars | ~200 | 4 |
| Sleep time per 200 chars | ~40 s | ~2 s |
| Total time (3 universes) | ~5 min | ~30 s |

Batching uses the MediaWiki `titles=A|B|C` parameter (up to 50 pages per request).
