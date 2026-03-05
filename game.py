import time
import os

from config import TICK_SPEED
from world import World


def clear():
    os.system("clear")


world = World()

try:
    while True:
        clear()

        world.update()
        grid = world.generate_grid()

        for row in grid:
            print(" ".join(row))

        print("\n===== WORLD DASHBOARD =====")
        print(f"Tick: {world.tick}")
        print(f"Agenti vivi: {len(world.agents)}")
        print(f"Cibo in mappa: {len(world.food)}")

        # indicatori ecosistema
        if len(world.agents) > 0:
            food_per_agent = len(world.food) / len(world.agents)
        else:
            food_per_agent = 0

        if world.last_births > world.last_deaths:
            trend = "growing"
        elif world.last_births < world.last_deaths:
            trend = "shrinking"
        else:
            trend = "stable"

        if food_per_agent < 0.5:
            starvation = "HIGH"
        elif food_per_agent < 1:
            starvation = "medium"
        else:
            starvation = "low"

        print(f"\nFood per agent: {food_per_agent:.2f}")
        print(f"Population trend: {trend}")
        print(f"Starvation risk: {starvation}")

        print(f"\nNascite (tick): {world.last_births} | Totali: {world.total_births}")
        print(f"Morti   (tick): {world.last_deaths} | Totali: {world.total_deaths}")
        print(f"Cibo mangiato (tick): {world.last_eaten} | Totale: {world.total_eaten}")

        time.sleep(TICK_SPEED)

except KeyboardInterrupt:

    print("\n\n===== SIMULATION REPORT =====")
    print(f"Tick totali: {world.tick}")
    print(f"Agenti vivi finali: {len(world.agents)}")
    print(f"Nascite totali: {world.total_births}")
    print(f"Morti totali: {world.total_deaths}")
    print(f"Cibo mangiato totale: {world.total_eaten}")
    print("\nSimulazione terminata 👋")