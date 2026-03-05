import asyncio
from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from config import TICK_SPEED, WIDTH, HEIGHT
from world import World

app = FastAPI()
world = World()

# loop simulazione
async def tick_loop():
    while True:
        world.update()
        await asyncio.sleep(TICK_SPEED)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(tick_loop())

# HOME: serve il client come HTML vero
@app.get("/")
def home():
    return FileResponse("client.html", media_type="text/html")

# (opzionale) anche /client.html
@app.get("/client.html")
def client():
    return FileResponse("client.html", media_type="text/html")

# API stato mondo
@app.get("/state")
def get_state():
    agents = [{"x": a.x, "y": a.y, "hunger": a.hunger} for a in world.agents]
    food = [{"x": fx, "y": fy} for (fx, fy) in world.food]

    return {
        "tick": world.tick,
        "agents_alive": len(world.agents),
        "food_count": len(world.food),
        "last_births": world.last_births,
        "last_deaths": world.last_deaths,
        "last_eaten": world.last_eaten,
        "total_births": world.total_births,
        "total_deaths": world.total_deaths,
        "total_eaten": world.total_eaten,
        "agents": agents,
        "food": food,
        "width": WIDTH,
        "height": HEIGHT,
    }

# debug ASCII
@app.get("/grid", response_class=PlainTextResponse)
def grid():
    grid = world.generate_grid()
    return "\n".join([" ".join(row) for row in grid])

# Static per future risorse (img/js/css)
app.mount("/static", StaticFiles(directory="."), name="static")