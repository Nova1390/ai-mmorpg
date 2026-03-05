from config import WIDTH, HEIGHT

class Agent:
    def __init__(self, x, y, brain):
        self.x = x
        self.y = y
        self.hunger = 20
        self.alive = True
        self.brain = brain

    def update(self, world):
        dx, dy = self.brain.decide(self, world)

        self.x = max(0, min(WIDTH - 1, self.x + dx))
        self.y = max(0, min(HEIGHT - 1, self.y + dy))

        self.hunger -= 1
        if self.hunger <= 0:
            self.alive = False

    def eat(self):
        self.hunger += 10
