import random
from config import WIDTH, HEIGHT, NUM_AGENTS, NUM_FOOD
from agent import Agent
from brain import RandomBrain

class World:
    def __init__(self):
        self.agents = [
    Agent(
        random.randint(0, WIDTH-1),
        random.randint(0, HEIGHT-1),
        RandomBrain()
    )
    for _ in range(NUM_AGENTS)
]

        self.food = {
            (random.randint(0, WIDTH-1), random.randint(0, HEIGHT-1))
            for _ in range(NUM_FOOD)
        }

    def update(self):
        alive_agents = []

        for agent in self.agents:
            agent.update(self)

            if (agent.x, agent.y) in self.food:
                agent.eat()
                self.food.remove((agent.x, agent.y))

            if agent.alive:
                alive_agents.append(agent)

        self.agents = alive_agents

    def generate_grid(self):
        grid = [["." for _ in range(WIDTH)] for _ in range(HEIGHT)]

        for fx, fy in self.food:
            grid[fy][fx] = "F"

        for agent in self.agents:
            grid[agent.y][agent.x] = "A"

        return grid
