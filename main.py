"""SoundRack — API FastAPI + servidor do frontend estático."""
import logging
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # credenciais vêm do ambiente / .env, nunca do código

import db  # noqa: E402  (depois do load_dotenv para respeitar SOUNDRACK_DB)
from spotify import MusicResolver  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

ASSETS_DIR = BASE_DIR / "assets"
CLOTHES_DIR = ASSETS_DIR / "clothes"
STATIC_DIR = BASE_DIR / "static"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg"}


# ------------------------------------------------------------------ imagens
def _norm(value: str) -> str:
    """NFC + minúsculas: o macOS grava 'ç' decomposto (NFD), o SQL guarda NFC."""
    return unicodedata.normalize("NFC", value).casefold()


def image_index() -> dict[str, str]:
    """Mapa 'nome sem extensão (normalizado)' -> nome real do ficheiro no disco."""
    index: dict[str, str] = {}
    if CLOTHES_DIR.is_dir():
        for path in sorted(CLOTHES_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                index.setdefault(_norm(path.stem), path.name)
    return index


# ------------------------------------------------------------------ serialização
def _basic_track(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "track_id": t["track_id"],
        "title": t["title"],
        "artist": t["artist"],
        "album": t["album"],
        "is_primary": bool(t["is_primary"]),
    }


def public_item(row, images: dict[str, str], tracks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "brand": row["brand"],
        "style": row["style"],
        "category": row["category"],
        "details": row["details"],
        "file_stem": row["file_stem"],
        # nome real do ficheiro; o frontend aplica encodeURIComponent
        "image_file": images.get(_norm(row["file_stem"])),
        "tracks": tracks,
    }


# ------------------------------------------------------------------ app
@asynccontextmanager
async def lifespan(app: FastAPI):
    created = db.init_db()
    if created:
        logging.getLogger("soundrack").info("Base criada em %s", db.DB_PATH)
    app.state.music = MusicResolver()
    await app.state.music.start()
    missing = [
        r["file_stem"] for r in db.list_items() if _norm(r["file_stem"]) not in image_index()
    ]
    if missing:
        logging.getLogger("soundrack").warning(
            "Sem ficheiro de imagem em assets/clothes/ para: %s", ", ".join(missing)
        )
    yield
    await app.state.music.aclose()


app = FastAPI(title="SoundRack", version="1.0.0", lifespan=lifespan)


@app.get("/api/items")
def api_items(style: Optional[str] = Query(None, description="Filtra por estilo (Trap, Rock, Streetwear)")):
    """Lista leve: não consulta o Spotify (isso acontece em /api/items/{id})."""
    rows = db.list_items(style)
    images = image_index()
    tracks = db.tracks_for_items([r["id"] for r in rows])
    return [
        public_item(r, images, [_basic_track(t) for t in tracks.get(r["id"], [])])
        for r in rows
    ]


@app.get("/api/items/{item_id}")
async def api_item(item_id: int, request: Request):
    row = db.get_item(item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    tracks = db.tracks_for_items([item_id]).get(item_id, [])
    music = await request.app.state.music.resolve_many(tracks)  # nunca levanta exceção
    data = public_item(row, image_index(), music)
    data["primary_track"] = next((t for t in music if t["is_primary"]), music[0] if music else None)
    return data


@app.get("/api/styles")
def api_styles():
    return db.list_styles()


@app.get("/api/health")
def api_health(request: Request):
    return {"ok": True, "music": request.app.state.music.status()}


# ------------------------------------------------------------------ estáticos
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
CLOTHES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# StaticFiles decodifica o percent-encoding do URL, então espaços e 'ç' funcionam.
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
