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
                                         │  Visualization   │
                                         │  (Pyvis → HTML)  │
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
| Visualization | [Pyvis](https://pyvis.readthedocs.io/) | Interactive HTML graph, opens in the browser |
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
pip install -r requirements.txt
```

### 2. Copy env config

```bash
cp .env.example .env   # credentials are already filled in for local Neo4j
```

### 3. Start Neo4j

```bash
docker compose up -d
# Neo4j browser UI: http://localhost:7474
```

### 4. Run the pipeline

```bash
python flows/ingest.py                   # Harry Potter, 200 characters (~3 min)
python flows/ingest.py harrypotter 500   # Harry Potter, 500 characters
python flows/ingest.py lotr 300          # Lord of the Rings
```

### 5. Open the visualization

```bash
python visualize.py                      # saves graph.html, prints the file:// URL
python visualize.py --universe lotr --max-nodes 150
```

---

## Project structure

```
fandom-knowledge-graph/
├── flows/
│   ├── __init__.py
│   ├── ingest.py          # Prefect flow: API → parse → Neo4j
│   ├── parse.py           # infobox parsing (no Prefect, independently testable)
│   └── load.py            # Neo4j write logic (no Prefect, independently testable)
├── config/
│   └── universes.yaml     # universe configs: API URL, categories, field→edge mappings
├── visualize.py           # generates an interactive HTML graph via Pyvis
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

## Roadmap

- [ ] Base pipeline: API → parse → Neo4j
- [ ] Pyvis visualization
- [ ] Multi-universe config
- [ ] Cross-universe graph (connections via shared races / archetypes)
- [ ] Web UI (FastAPI + D3.js)
- [ ] Export to GraphML / JSON for Gephi
