# fandom-knowledge-graph

A knowledge graph of characters and their relationships across fictional universes, built from Fandom wiki data.

**[View interactive graph →](https://AnnaShw.github.io/fandom-knowledge-graph/graph.html)**

The pipeline fetches pages via the official MediaWiki API, parses infoboxes, and builds a social network of characters — no scraping, no ban risk.

---

## How it works

```
Fandom Wiki API
     │  batch fetch (50 pages/request)
     ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│  Ingestion  │────▶│   Parsing    │────▶│  JSON cache  │────▶│  Plotly dashboard │
│  (Prefect)  │     │  (infoboxes) │     │  cache/*.json│     │  (standalone HTML)│
└─────────────┘     └──────────────┘     └──────────────┘     └───────────────────┘
       │
       ▼ optional
┌───────────────┐
│  Neo4j        │
│  (Docker)     │
└───────────────┘
```

Analytics (PageRank, Louvain community detection) are computed during ingestion and embedded in the JSON cache. Visualization reads the cache directly — no database connection needed.

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
| Visualization | [Plotly](https://plotly.com/python/) | Interactive multi-panel dashboard, saved as standalone HTML |
| CI refresh | GitHub Actions | Runs ingestion weekly, commits updated cache |
| Language | Python 3.12+ | |

---

## Supported universes

| Universe | Wiki | Method |
|---|---|---|
| Harry Potter | `harrypotter.fandom.com` | Template: `Individual infobox` |
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
pip install -r requirements.txt
python visualize.py --universe harrypotter
```

Opens `graph.html` — a fully self-contained Plotly dashboard.

---

### Option B — Re-ingest locally (requires Docker for Neo4j)

```bash
# 1. Install
pip install -r requirements.txt

# 2. Start Neo4j
docker compose up -d

# 3. Ingest (Neo4j + cache)
python flows/ingest.py harrypotter 300 --clear
python flows/ingest.py dune 300 --clear

# 4. Visualize
python visualize.py --universe harrypotter --max-nodes 200
```

The `--clear` flag deletes existing data for that universe before re-ingesting.  
The `--cache-only` flag skips Neo4j entirely and only writes the JSON cache (used by CI).

---

## Visualization

`visualize.py` reads from the JSON cache and generates a single-file interactive HTML dashboard:

| Panel | What it shows |
|---|---|
| **Character network** | Force-directed graph (spring layout via NetworkX); nodes sized by PageRank, colored by detected community |
| **Bridge characters** | Horizontal bar chart of characters with the highest betweenness centrality — those who connect different factions |
| **Community distribution** | Pie chart of auto-detected factions/houses and their sizes |

Hover any node to see its rank, community, and connection count. Top 15 characters by PageRank are labeled directly on the graph.

### Why this is useful for understanding the story

Fictional universes are built around relationships — alliances, rivalries, families, betrayals. The graph makes those structures visible at a glance:

- **Node size = narrative importance.** PageRank rewards characters who are connected to other well-connected characters, not just those with the most raw links. Dumbledore and Voldemort rank high not because they appear everywhere, but because the characters they touch are themselves central to the story.
- **Color = faction.** Community detection runs without any prior knowledge of houses, sides, or allegiances — it infers them purely from the relationship graph. Seeing Gryffindor, Death Eaters, and the Order of the Phoenix emerge as distinct color clusters confirms the story's natural faction structure.
- **Bridge characters = pivotal figures.** Characters with high betweenness (the bar chart) sit on the shortest paths between factions. In Harry Potter, Snape and Dumbledore score high here — exactly the characters whose dual loyalties drive the plot. A character who bridges many communities is often the one whose choices change the story.
- **Proximity = shared world.** Nodes that cluster together have overlapping social circles. Characters who appear far apart on the graph rarely interact — useful for spotting isolated subplots or characters who exist mostly within one faction bubble.

```bash
py visualize.py --universe harrypotter   # default: 300 nodes → graph.html
py visualize.py --universe dune --max-nodes 150 --output dune.html
```

---

## Graph analytics

After each ingestion run, the following metrics are computed and embedded in the JSON cache:

| Metric | Algorithm | Effect |
|---|---|---|
| **PageRank** | Pure-Python power iteration | Node size — narratively important characters appear larger even with few direct links |
| **Community detection** | Louvain (via NetworkX) | Node color — auto-discovered factions/houses get distinct colors |
| **Rank** | Sorted by PageRank | Shown on hover: "Rank #3 / 300" |

---

## Automatic cache refresh (GitHub Actions)

The workflow in `.github/workflows/refresh-cache.yml` runs every Monday at 03:00 UTC:

1. Fetches fresh data from all wiki APIs
2. Writes updated `cache/*.json`
3. Commits and pushes the changes
4. Updates visualizetion

You can also trigger it manually from the **Actions** tab.

---

## Project structure

```
fandom-knowledge-graph/
├── flows/
│   ├── ingest.py          # Prefect flow: API → parse → Neo4j + JSON cache
│   ├── parse.py           # infobox parsing (no Prefect, independently testable)
│   ├── load.py            # Neo4j write logic (no Prefect, independently testable)
│   └── analytics.py       # PageRank + Louvain community detection (pure Python)
├── cache/
│   ├── harrypotter.json   # pre-built graph data (committed to repo)
│   
├── config/
│   └─── universes.yaml     # universe configs + global field aliases
├── .github/
│   └── workflows/
│       └── refresh-cache.yml  # weekly CI job
├── visualize.py           # Plotly dashboard generator → graph.html
├── docker-compose.yml
├── requirements.txt
├── .env                   # local credentials (do not commit)
└── .env.example
```

