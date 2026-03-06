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


app = FastAPI()

world = World()

npc_brain = FoodBrain(vision_radius=8)
planner = Planner(model="phi3")
player_brain = LLMBrain(planner=planner, fallback=npc_brain, think_every_ticks=60)
leader_brain = LLMBrain(planner=planner, fallback=npc_brain, think_every_ticks=120)

SPRITES_DIR = "sprites"
app.mount("/sprites", StaticFiles(directory=SPRITES_DIR), name="sprites")


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
    alive_agents = [a for a in world.agents if a.alive]

    players = [a for a in alive_agents if a.is_player]
    npcs = [a for a in alive_agents if not a.is_player]

    avg_hunger = 0
    if alive_agents:
        avg_hunger = sum(a.hunger for a in alive_agents) / len(alive_agents)

    return {
        "tick": world.tick,
        "width": world.width,
        "height": world.height,
        "tiles": world.tiles,
        "food": [{"x": x, "y": y} for x, y in world.food],
        "wood": [{"x": x, "y": y} for x, y in world.wood],
        "stone": [{"x": x, "y": y} for x, y in world.stone],
        "structures": [{"x": x, "y": y} for x, y in world.structures],
        "villages": world.villages,
        "agents": [
            {
                "x": a.x,
                "y": a.y,
                "is_player": a.is_player,
                "player_id": a.player_id,
                "role": getattr(a, "role", "npc"),
                "village_id": getattr(a, "village_id", None),
            }
            for a in alive_agents
        ],
        "population": len(alive_agents),
        "players": len(players),
        "npcs": len(npcs),
        "avg_hunger": round(avg_hunger, 2),
        "food_count": len(world.food),
        "wood_count": len(world.wood),
        "stone_count": len(world.stone),
        "houses_count": len(world.structures),
        "villages_count": len(world.villages),
        "leaders_count": world.count_leaders(),
        "llm_interactions": world.llm_interactions,
    }


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
                "x": p.x,
                "y": p.y,
                "hunger": p.hunger,
                "goal": getattr(p, "goal", "survive"),
                "role": getattr(p, "role", "player"),
                "village_id": getattr(p, "village_id", None),
                "inventory": {
                    "food": inv.get("food", 0),
                    "wood": inv.get("wood", 0),
                    "stone": inv.get("stone", 0),
                },
            }

    raise HTTPException(status_code=404, detail="player not found")