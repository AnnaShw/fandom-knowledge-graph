"""
Neo4j loading logic — no Prefect dependencies, fully testable in isolation.
"""
from collections import defaultdict

from neo4j import GraphDatabase


def get_driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def setup_indexes(driver) -> None:
    with driver.session() as session:
        session.run(
            "CREATE INDEX character_name IF NOT EXISTS "
            "FOR (c:Character) ON (c.name)"
        )


def load_characters(driver, characters: list[dict], universe: str) -> None:
    """
    Upsert all characters and their relationships into Neo4j.

    Each item in `characters` must be:
        {"name": str, "relations": {rel_type: [target_name, ...]}}
    """
    with driver.session() as session:
        # Upsert all character nodes in one query
        session.run(
            "UNWIND $chars AS c MERGE (:Character {name: c.name, universe: c.universe})",
            chars=[{"name": c["name"], "universe": universe} for c in characters],
        )

        # Group relationships by type then upsert each group in one query.
        # rel_type comes from universes.yaml — controlled input, safe to interpolate.
        by_rel: dict[str, list] = defaultdict(list)
        for char in characters:
            for rel_type, targets in char["relations"].items():
                for target in targets:
                    by_rel[rel_type].append({"src": char["name"], "tgt": target, "u": universe})

        for rel_type, rows in by_rel.items():
            session.run(
                f"UNWIND $rows AS r "
                f"MERGE (a:Character {{name: r.src, universe: r.u}}) "
                f"MERGE (b:Character {{name: r.tgt, universe: r.u}}) "
                f"MERGE (a)-[:{rel_type}]->(b)",
                rows=rows,
            )
