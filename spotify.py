"""Resolve capa, preview e links de cada faixa.

Fontes, por ordem:
  1. Spotify Web API (Client Credentials) — capa, link e, quando existir, preview_url.
  2. iTunes Search API (sem credenciais) — apenas para preencher o que o Spotify
     não devolveu. O Spotify deixou de fornecer preview_url para muitas apps
     novas, por isso este fallback mantém o player funcional.

Nenhuma falha (credenciais inválidas, rate limit, rede, JSON estranho) levanta
exceção para fora desta classe: o resultado é sempre um dicionário, com os
campos de mídia a None quando não foi possível resolvê-los.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

log = logging.getLogger("soundrack.music")

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
ITUNES_URL = "https://itunes.apple.com/search"

OK_TTL = 6 * 3600   # resultados com sucesso ficam 6 h em cache
FAIL_TTL = 60       # falhas são repetidas ao fim de 1 min


def _empty_media() -> dict[str, Any]:
    return {
        "cover_url": None,
        "preview_url": None,
        "preview_source": None,
        "spotify_url": None,
        "album": None,
        "matched_title": None,
        "source": None,
    }


class MusicResolver:
    def __init__(self) -> None:
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
        self.market = os.getenv("SPOTIFY_MARKET", "BR").strip() or "BR"
        self.use_itunes = os.getenv("ITUNES_FALLBACK", "true").strip().lower() not in {
            "0", "false", "no", "off",
        }
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        self._token_expires = 0.0
        self._blocked_until = 0.0          # rate limit ou credenciais inválidas
        self._block_reason: Optional[str] = None
        self._token_lock = asyncio.Lock()
        self._cache: dict[int, tuple[float, dict[str, Any]]] = {}

    # ------------------------------------------------------------ ciclo de vida
    @property
    def spotify_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0),
            headers={"User-Agent": "SoundRack/1.0"},
        )
        if not self.spotify_configured:
            log.warning(
                "Credenciais do Spotify ausentes (SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET). "
                "O app funciona, mas capas/previews virão apenas do fallback iTunes."
            )

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()

    def status(self) -> dict[str, Any]:
        now = time.time()
        return {
            "spotify_configured": self.spotify_configured,
            "spotify_blocked": now < self._blocked_until,
            "spotify_block_reason": self._block_reason if now < self._blocked_until else None,
            "itunes_fallback": self.use_itunes,
            "cached_tracks": len(self._cache),
        }

    # ------------------------------------------------------------ Spotify
    @staticmethod
    def _retry_after(resp: httpx.Response) -> float:
        try:
            return max(1.0, min(float(resp.headers.get("Retry-After", "30")), 3600.0))
        except ValueError:
            return 30.0

    def _block(self, seconds: float, reason: str) -> None:
        self._blocked_until = time.time() + seconds
        self._block_reason = reason

    async def _get_token(self) -> Optional[str]:
        if not self.spotify_configured or self._client is None:
            return None
        if time.time() < self._blocked_until:
            return None
        if self._token and time.time() < self._token_expires - 30:
            return self._token
        async with self._token_lock:
            if self._token and time.time() < self._token_expires - 30:
                return self._token
            try:
                resp = await self._client.post(
                    TOKEN_URL,
                    data={"grant_type": "client_credentials"},
                    auth=(self.client_id, self.client_secret),
                )
            except httpx.HTTPError as exc:
                log.warning("Falha de rede ao pedir token do Spotify: %s", exc)
                self._block(30, "rede indisponível")
                return None
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    self._token = data["access_token"]
                    self._token_expires = time.time() + int(data.get("expires_in", 3600))
                    return self._token
                except (ValueError, KeyError):
                    self._block(60, "resposta de token inválida")
                    return None
            if resp.status_code in (400, 401):
                log.error("Credenciais do Spotify inválidas (HTTP %s).", resp.status_code)
                self._block(600, "credenciais inválidas")
            elif resp.status_code == 429:
                self._block(self._retry_after(resp), "rate limit")
            else:
                log.warning("Token do Spotify devolveu HTTP %s", resp.status_code)
                self._block(60, f"HTTP {resp.status_code}")
            return None

    async def _spotify_get(
        self, path: str, params: dict[str, Any], _retry: bool = True
    ) -> Optional[dict[str, Any]]:
        token = await self._get_token()
        if not token or self._client is None:
            return None
        try:
            resp = await self._client.get(
                f"{API_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            log.warning("Falha de rede no Spotify: %s", exc)
            return None
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return None
        if resp.status_code == 401 and _retry:
            self._token = None
            return await self._spotify_get(path, params, _retry=False)
        if resp.status_code == 429:
            self._block(self._retry_after(resp), "rate limit")
        else:
            log.info("Spotify %s devolveu HTTP %s", path, resp.status_code)
        return None

    @staticmethod
    def _media_from_spotify(track: dict[str, Any]) -> dict[str, Any]:
        media = _empty_media()
        album = track.get("album") or {}
        images = album.get("images") or []
        media["cover_url"] = images[0].get("url") if images else None
        media["album"] = album.get("name")
        media["matched_title"] = track.get("name")
        media["spotify_url"] = (track.get("external_urls") or {}).get("spotify")
        media["preview_url"] = track.get("preview_url")
        if media["preview_url"]:
            media["preview_source"] = "spotify"
        return media

    async def _search_spotify(self, title: Optional[str], artist: str) -> Optional[dict[str, Any]]:
        def clean(value: str) -> str:
            return value.replace('"', " ")

        if title:
            queries = [f'track:"{clean(title)}" artist:"{clean(artist)}"', f"{title} {artist}"]
        else:
            queries = [f'artist:"{clean(artist)}"']

        for query in queries:
            data = await self._spotify_get(
                "/search",
                {"q": query, "type": "track", "limit": 5, "market": self.market},
            )
            if data is None:
                return None
            items = (data.get("tracks") or {}).get("items") or []
            if not items:
                continue
            best = items[0]
            if not best.get("preview_url"):
                same_name = (best.get("name") or "").lower()
                best = next(
                    (
                        i for i in items
                        if i.get("preview_url") and (i.get("name") or "").lower() == same_name
                    ),
                    best,
                )
            return self._media_from_spotify(best)
        return None

    # ------------------------------------------------------------ iTunes
    async def _search_itunes(self, title: Optional[str], artist: str) -> Optional[dict[str, Any]]:
        if self._client is None:
            return None
        term = f"{title} {artist}" if title else artist
        try:
            resp = await self._client.get(
                ITUNES_URL,
                params={"term": term, "media": "music", "entity": "song", "limit": 8, "country": "BR"},
            )
            if resp.status_code != 200:
                return None
            results = resp.json().get("results") or []
        except (httpx.HTTPError, ValueError):
            return None

        with_preview = [r for r in results if r.get("previewUrl")]
        if not with_preview:
            return None
        wanted = artist.lower()
        best = next(
            (r for r in with_preview if wanted in (r.get("artistName") or "").lower()),
            with_preview[0],
        )
        artwork = best.get("artworkUrl100")
        if artwork:
            artwork = artwork.replace("100x100bb", "600x600bb")
        media = _empty_media()
        media.update(
            cover_url=artwork,
            preview_url=best.get("previewUrl"),
            preview_source="itunes",
            album=best.get("collectionName"),
            matched_title=best.get("trackName"),
        )
        return media

    # ------------------------------------------------------------ público
    async def _lookup(self, track: dict[str, Any]) -> dict[str, Any]:
        media = _empty_media()
        title, artist = track.get("title"), track["artist"]

        if self.spotify_configured:
            spotify: Optional[dict[str, Any]] = None
            if track.get("spotify_id"):
                data = await self._spotify_get(f"/tracks/{track['spotify_id']}", {"market": self.market})
                spotify = self._media_from_spotify(data) if data else None
            if spotify is None:
                spotify = await self._search_spotify(title, artist)
            if spotify:
                media.update(spotify)
                media["source"] = "spotify"

        if self.use_itunes and (not media["preview_url"] or not media["cover_url"]):
            itunes = await self._search_itunes(title, artist)
            if itunes:
                if not media["preview_url"]:
                    media["preview_url"] = itunes["preview_url"]
                    media["preview_source"] = "itunes"
                if not media["cover_url"]:
                    media["cover_url"] = itunes["cover_url"]
                media["album"] = media["album"] or itunes["album"]
                media["matched_title"] = media["matched_title"] or itunes["matched_title"]
                media["source"] = media["source"] or "itunes"
        return media

    async def resolve(self, track: dict[str, Any]) -> dict[str, Any]:
        """Devolve a faixa com os campos de mídia preenchidos (ou None)."""
        key = track["track_id"]
        cached = self._cache.get(key)
        if cached and cached[0] > time.time():
            media = cached[1]
        else:
            try:
                media = await self._lookup(track)
            except Exception:  # noqa: BLE001 — nunca derrubar a resposta
                log.exception("Erro inesperado ao resolver a faixa %s", key)
                media = _empty_media()
            ok = bool(media["cover_url"] or media["preview_url"])
            self._cache[key] = (time.time() + (OK_TTL if ok else FAIL_TTL), media)

        return {
            "track_id": key,
            "title": track.get("title") or media["matched_title"],
            "artist": track["artist"],
            "album": media["album"] or track.get("album"),
            "is_primary": bool(track.get("is_primary")),
            "position": track.get("position"),
            "cover_url": media["cover_url"],
            "preview_url": media["preview_url"],
            "preview_source": media["preview_source"],
            "spotify_url": media["spotify_url"],
            "source": media["source"],
        }

    async def resolve_many(self, tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list(await asyncio.gather(*(self.resolve(t) for t in tracks)))
