iimport random

from config import (
    WIDTH, HEIGHT, NUM_AGENTS, NUM_FOOD,
    FOOD_RESPAWN_PER_TICK, MAX_FOOD,
    REPRO_MIN_HUNGER, REPRO_PROB, REPRO_COST, MAX_AGENTS,
)
from agent import Agent
from brain import FoodBrain


class World:
    def __init__(self):
        self.agents = [
            Agent(
                random.randint(0, WIDTH - 1),
                random.randint(0, HEIGHT - 1),
                FoodBrain()
            )
            for _ in range(NUM_AGENTS)
        ]

        self.food = {
            (random.randint(0, WIDTH - 1), random.randint(0, HEIGHT - 1))
            for _ in range(NUM_FOOD)
        }

    def update(self):
        alive_agents = []

        # 1) aggiorna agenti + mangiare
        for agent in self.agents:
            agent.update(self)

            if (agent.x, agent.y) in self.food:
                agent.eat()
                self.food.remove((agent.x, agent.y))

            if agent.alive:
                alive_agents.append(agent)

        self.agents = alive_agents

        # 2) riproduzione (se 2+ agenti stanno sulla stessa cella)
        if len(self.agents) < MAX_AGENTS:
            pos_map = {}
            for a in self.agents:
                pos_map.setdefault((a.x, a.y), []).append(a)

            babies = []
            for (x, y), group in pos_map.items():
                if len(group) < 2:
                    continue

                a1, a2 = group[0], group[1]

                can_repro = (
                    a1.hunger >= REPRO_MIN_HUNGER and
                    a2.hunger >= REPRO_MIN_HUNGER and
                    a1.repro_cooldown == 0 and
                    a2.repro_cooldown == 0
                )

                if can_repro and random.random() < REPRO_PROB:
                    # costo energetico
                    a1.hunger -= REPRO_COST
                    a2.hunger -= REPRO_COST

                    # cooldown
                    a1.repro_cooldown = 10
                    a2.repro_cooldown = 10

                    babies.append(Agent(x, y, FoodBrain()))

                if len(self.agents) + len(babies) >= MAX_AGENTS:
                    break

            self.agents.extend(babies)

        # 3) respawn cibo (mondo più "persistente")
        if len(self.food) < MAX_FOOD:
            for _ in range(FOOD_RESPAWN_PER_TICK):
                if len(self.food) >= MAX_FOOD:
                    break
                self.food.add((random.randint(0, WIDTH - 1), random.randint(0, HEIGHT - 1)))

    def generate_grid(self):
        grid = [["." for _ in range(WIDTH)] for _ in range(HEIGHT)]

        for fx, fy in self.food:
            grid[fy][fx] = "F"

        for agent in self.agents:
            grid[agent.y][agent.x] = "A"

        return grid