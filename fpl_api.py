import asyncio
import time
from typing import Any

import httpx

BASE = "https://fantasy.premierleague.com/api"
_CACHE: dict[str, tuple[float, Any]] = {}

async def get_json(path: str, ttl: int = 60) -> Any:
    now = time.time()
    if path in _CACHE and now - _CACHE[path][0] < ttl:
        return _CACHE[path][1]
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "Friends-FPL-Telegram-Bot/1.0"}) as client:
        r = await client.get(BASE + path)
        r.raise_for_status()
        data = r.json()
    _CACHE[path] = (now, data)
    return data

async def bootstrap() -> dict:
    return await get_json("/bootstrap-static/", ttl=300)

async def live(event_id: int) -> dict:
    return await get_json(f"/event/{event_id}/live/", ttl=30)

async def fixtures(event_id: int | None = None) -> list[dict]:
    path = "/fixtures/" if event_id is None else f"/fixtures/?event={event_id}"
    return await get_json(path, ttl=120)

async def refresh_cache() -> None:
    _CACHE.clear()
    await bootstrap()

def current_event(data: dict) -> dict:
    events = data.get("events", [])
    for e in events:
        if e.get("is_current"):
            return e
    for e in events:
        if e.get("is_next"):
            return e
    return max(events, key=lambda x: x["id"]) if events else {"id": 1, "name": "Gameweek 1"}

def player_map(data: dict) -> dict[int, dict]:
    return {p["id"]: p for p in data.get("elements", [])}

def team_map(data: dict) -> dict[int, dict]:
    return {t["id"]: t for t in data.get("teams", [])}

def type_map(data: dict) -> dict[int, dict]:
    return {t["id"]: t for t in data.get("element_types", [])}
