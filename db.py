"""Acesso ao SQLite com SQL puro (sem ORM).

Uso na linha de comandos:
    python db.py            # cria a base se ainda não existir
    python db.py --reset    # apaga e recria a base a partir de schema.sql
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("SOUNDRACK_DB", BASE_DIR / "soundrack.db"))
SCHEMA_PATH = BASE_DIR / "schema.sql"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force: bool = False) -> bool:
    """Cria e povoa a base. Devolve True se executou o schema.sql."""
    if force and DB_PATH.exists():
        DB_PATH.unlink()
    conn = connect()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'items'"
        ).fetchone()
        if exists:
            return False
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
        return True
    finally:
        conn.close()


# ---------------------------------------------------------------- consultas

ITEM_COLUMNS = "id, slug, file_stem, name, brand, style, category, details"


def list_items(style: Optional[str] = None) -> list[sqlite3.Row]:
    sql = f"SELECT {ITEM_COLUMNS} FROM items"
    params: list[Any] = []
    if style:
        sql += " WHERE style = ? COLLATE NOCASE"
        params.append(style)
    sql += " ORDER BY sort_order, id"
    conn = connect()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def get_item(item_id: int) -> Optional[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(
            f"SELECT {ITEM_COLUMNS} FROM items WHERE id = ?", (item_id,)
        ).fetchone()
    finally:
        conn.close()


def list_styles() -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT style, COUNT(*) AS count FROM items "
            "GROUP BY style ORDER BY count DESC, style"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def tracks_for_items(item_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Faixas de várias peças numa só consulta, agrupadas por item_id."""
    if not item_ids:
        return {}
    placeholders = ",".join("?" for _ in item_ids)
    sql = f"""
        SELECT it.item_id, it.position, it.is_primary,
               t.id AS track_id, t.title, t.artist, t.album, t.spotify_id
        FROM item_tracks it
        JOIN tracks t ON t.id = it.track_id
        WHERE it.item_id IN ({placeholders})
        ORDER BY it.item_id, it.position
    """
    conn = connect()
    try:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for row in conn.execute(sql, item_ids):
            grouped.setdefault(row["item_id"], []).append(dict(row))
        return grouped
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inicializa a base do SoundRack")
    parser.add_argument("--reset", action="store_true", help="apaga e recria a base")
    args = parser.parse_args()
    created = init_db(force=args.reset)
    print(f"Base em {DB_PATH}: {'criada' if created else 'já existia (use --reset para recriar)'}")
