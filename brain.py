import random

class RandomBrain:
    def decide(self, agent, world):
        dx = random.choice([-1, 0, 1])
        dy = random.choice([-1, 0, 1])
        return dx, dy
