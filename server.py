import asyncio
import random
import uuid
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from world import World
from agent import Agent
from brain import FoodBrain, LLMBrain
from planner import Planner
from state_serializer import (
    SCHEMA_VERSION,
    serialize_dynamic_world_state,
    serialize_static_world_state,
)
from config import LLM_ENABLED


app = FastAPI()

world = World()

npc_brain = FoodBrain(vision_radius=8)
planner = Planner(model="phi3")
if LLM_ENABLED:
    player_brain = LLMBrain(planner=planner, fallback=npc_brain, think_every_ticks=60)
    leader_brain = LLMBrain(planner=planner, fallback=npc_brain, think_every_ticks=240)
else:
    player_brain = npc_brain
    leader_brain = npc_brain

SPRITES_DIR = "sprites"
FRONTEND_DIR = "frontend"

app.mount("/sprites", StaticFiles(directory=SPRITES_DIR), name="sprites")
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


def refresh_agent_brains():
    for a in world.agents:
        if not a.alive:
            continue

        if a.is_player:
            a.brain = player_brain
            a.role = "player"
        elif getattr(a, "role", "npc") == "leader":
            a.brain = leader_brain
        else:
            a.brain = npc_brain


async def tick_loop():
    while True:
        refresh_agent_brains()
        world.update()
        refresh_agent_brains()
        await asyncio.sleep(0.2)


@app.on_event("startup")
async def startup():
    for _ in range(40):
        for _ in range(200):
            x = random.randint(0, world.width - 1)
            y = random.randint(0, world.height - 1)

            if world.is_walkable(x, y) and not world.is_occupied(x, y):
                npc = Agent(x, y, npc_brain, False, None)
                npc.role = "npc"
                world.add_agent(npc)
                break

    asyncio.create_task(tick_loop())


@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/client")
def old_client():
    return FileResponse("client.html")


@app.get("/sprites_manifest")
def sprites_manifest():
    manifest = {}

    for folder in os.listdir(SPRITES_DIR):
        path = os.path.join(SPRITES_DIR, folder)

        if os.path.isdir(path):
            files = []

            for root, dirs, filenames in os.walk(path):
                for f in filenames:
                    if f.lower().endswith((".png", ".jpg", ".jpeg")):
                        rel = os.path.relpath(os.path.join(root, f), SPRITES_DIR)
                        files.append("/sprites/" + rel.replace("\\", "/"))

            manifest[folder.lower()] = files

    return manifest


@app.get("/state")
def get_state():
    return serialize_dynamic_world_state(world)


@app.get("/state/static")
def get_static_state():
    return serialize_static_world_state(world)


@app.get("/state/events")
def get_events(since_tick: int = -1):
    events = world.get_events_since(since_tick)
    retained = world.events
    oldest_tick = retained[0]["tick"] if retained else None
    newest_tick = retained[-1]["tick"] if retained else None
    return {
        "schema_version": SCHEMA_VERSION,
        "events": events,
        "oldest_retained_tick": oldest_tick,
        "newest_retained_tick": newest_tick,
        "retained_event_count": len(retained),
    }


@app.get("/debug/metrics")
def get_debug_metrics():
    if hasattr(world, "metrics_collector"):
        return world.metrics_collector.latest()
    return {}


@app.get("/debug/history")
def get_debug_history(limit: int = 120):
    if hasattr(world, "metrics_collector"):
        return {
            "tick": int(getattr(world, "tick", 0)),
            "history": world.metrics_collector.history(limit=limit),
        }
    return {"tick": int(getattr(world, "tick", 0)), "history": []}


@app.post("/spawn_player")
def spawn_player():
    for _ in range(200):
        x = random.randint(0, world.width - 1)
        y = random.randint(0, world.height - 1)

        if world.is_walkable(x, y) and not world.is_occupied(x, y):
            pid = str(uuid.uuid4())

            player = Agent(x, y, player_brain, True, pid)
            player.role = "player"
            world.add_agent(player)

            return {"player_id": pid}

    return {"error": "spawn failed"}


@app.get("/player/{player_id}")
def get_player(player_id: str):
    for p in world.agents:
        if p.player_id == player_id and p.alive:
            inv = getattr(p, "inventory", {})
            return {
                "id": p.player_id,
                "agent_id": p.agent_id,
                "x": p.x,
                "y": p.y,
                "hunger": p.hunger,
                "goal": getattr(p, "goal", "survive"),
                "role": getattr(p, "role", "player"),
                "village_id": getattr(p, "village_id", None),
                "task": getattr(p, "task", "idle"),
                "inventory": {
                    "food": inv.get("food", 0),
                    "wood": inv.get("wood", 0),
                    "stone": inv.get("stone", 0),
                },
            }

    raise HTTPException(status_code=404, detail="player not found")
