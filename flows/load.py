"""
Neo4j loading logic — no Prefect dependencies, fully testable in isolation.
"""
from neo4j import GraphDatabase


def get_driver(uri: str, user: str, password: str):
    return GraphDatabase.driver(uri, auth=(user, password))


def setup_indexes(driver) -> None:
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT character_pk IF NOT EXISTS "
            "FOR (c:Character) REQUIRE (c.name, c.universe) IS NODE KEY"
        )


def _upsert_character(tx, name: str, universe: str) -> None:
    tx.run(
        "MERGE (c:Character {name: $name, universe: $universe})",
        name=name, universe=universe,
    )


def _upsert_relationship(tx, source: str, target: str, rel_type: str, universe: str) -> None:
    # rel_type comes from universes.yaml — controlled input, safe to interpolate
    query = (
        f"MERGE (a:Character {{name: $src, universe: $u}}) "
        f"MERGE (b:Character {{name: $tgt, universe: $u}}) "
        f"MERGE (a)-[:{rel_type}]->(b)"
    )
    tx.run(query, src=source, tgt=target, u=universe)


def load_characters(driver, characters: list[dict], universe: str) -> None:
    """
    Upsert all characters and their relationships into Neo4j.

    Each item in `characters` must be:
        {"name": str, "relations": {rel_type: [target_name, ...]}}
    """
    with driver.session() as session:
        for char in characters:
            session.execute_write(_upsert_character, char["name"], universe)
            for rel_type, targets in char["relations"].items():
                for target in targets:
                    session.execute_write(
                        _upsert_relationship, char["name"], target, rel_type, universe
                    )
