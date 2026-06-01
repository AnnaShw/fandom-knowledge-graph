"""
Prefect flow: MediaWiki API → parse infoboxes → Neo4j.

Usage (from project root):
    python flows/ingest.py                        # Harry Potter, 200 chars
    python flows/ingest.py harrypotter 500        # Harry Potter, 500 chars
    python flows/ingest.py lotr 300               # Lord of the Rings, 300 chars
"""
import os
import sys
import time
from pathlib import Path

# Ensure the project root is on the path regardless of where the script is invoked from
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import requests
from dotenv import load_dotenv
from prefect import flow, task
from prefect.logging import get_run_logger

from flows.parse import parse_character
from flows.load import get_driver, setup_indexes, load_characters

load_dotenv()

CONFIG_PATH = Path(__file__).parent.parent / "config" / "universes.yaml"
HEADERS = {"User-Agent": "fandom-knowledge-graph/1.0 (educational project)"}

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "fandom123")


def _load_config(universe_key: str) -> dict:
    with open(CONFIG_PATH) as f:
        all_configs = yaml.safe_load(f)
    if universe_key not in all_configs:
        available = list(all_configs.keys())
        raise ValueError(f"Unknown universe '{universe_key}'. Available: {available}")
    return all_configs[universe_key]


@task(retries=3, retry_delay_seconds=10)
def fetch_by_template(api_url: str, template: str, limit: int) -> list[str]:
    """Fetch up to `limit` page titles that embed a given infobox template."""
    logger = get_run_logger()
    titles = []
    params = {
        "action": "query",
        "generator": "embeddedin",
        "geititle": f"Template:{template}",
        "geilimit": 500,
        "geinamespace": 0,   # main namespace only (no talk pages, templates, etc.)
        "format": "json",
    }
    while len(titles) < limit:
        resp = requests.get(api_url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("query", {}).get("pages", {}).values()
        titles.extend(p["title"] for p in batch if p.get("ns") == 0)
        logger.info(f"  discovered {len(titles)} titles so far...")
        if "continue" not in data:
            break
        params.update(data["continue"])
        time.sleep(0.3)
    return titles[:limit]


@task(retries=3, retry_delay_seconds=10)
def fetch_by_category(api_url: str, category: str, limit: int) -> list[str]:
    """Fetch up to `limit` page titles from a wiki category."""
    logger = get_run_logger()
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": 500,
        "cmtype": "page",
        "format": "json",
    }
    while len(titles) < limit:
        resp = requests.get(api_url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data["query"]["categorymembers"]
        titles.extend(m["title"] for m in batch)
        logger.info(f"  discovered {len(titles)} titles so far...")
        if "continue" not in data:
            break
        params.update(data["continue"])
        time.sleep(0.3)
    return titles[:limit]


@task(retries=3, retry_delay_seconds=5)
def fetch_wikitext(api_url: str, title: str) -> str:
    """Fetch the raw wikitext of a single page."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
    }
    resp = requests.get(api_url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    page = next(iter(data["query"]["pages"].values()))
    if "revisions" not in page:
        return ""
    rev = page["revisions"][0]
    # Support both old-style rev["*"] and new-style rev["slots"]["main"]["*"]
    if "slots" in rev:
        return rev["slots"]["main"].get("*", "")
    return rev.get("*", "")


@flow(name="fandom-ingest", log_prints=True)
def ingest_universe(universe_key: str = "harrypotter", limit: int = 200):
    logger = get_run_logger()
    config = _load_config(universe_key)
    logger.info(f"Ingesting: {config['name']}  |  limit={limit}")

    # Step 1: discover character pages (template-based or category-based)
    if "character_template" in config:
        titles = fetch_by_template(config["api_url"], config["character_template"], limit)
    else:
        titles = fetch_by_category(config["api_url"], config["character_category"], limit)
    logger.info(f"Found {len(titles)} characters to process")

    # Step 2: fetch wikitext and parse each character
    characters = []
    for i, title in enumerate(titles):
        wikitext = fetch_wikitext(config["api_url"], title)
        if wikitext:
            relations = parse_character(wikitext, config["infobox_fields"])
            characters.append({"name": title, "relations": relations})
        if (i + 1) % 20 == 0:
            logger.info(f"  parsed {i + 1}/{len(titles)} ...")
        time.sleep(0.2)  # stay within API rate limits

    # Step 3: load into Neo4j
    driver = get_driver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        setup_indexes(driver)
        load_characters(driver, characters, universe_key)
    finally:
        driver.close()

    rel_count = sum(len(v) for c in characters for v in c["relations"].values())
    logger.info(f"Done! {len(characters)} characters, {rel_count} relationships loaded.")
    return {"characters": len(characters), "relationships": rel_count}


if __name__ == "__main__":
    universe = sys.argv[1] if len(sys.argv) > 1 else "harrypotter"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    ingest_universe(universe_key=universe, limit=limit)
