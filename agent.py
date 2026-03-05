from config import WIDTH, HEIGHT, AGENT_START_HUNGER, FOOD_EAT_GAIN


class Agent:
    def __init__(self, x, y, brain):
        self.x = x
        self.y = y
        self.brain = brain

        self.hunger = AGENT_START_HUNGER
        self.alive = True

        # per evitare che si riproducano a raffica
        self.repro_cooldown = 0

    def update(self, world):
        dx, dy = self.brain.decide(self, world)

        self.x = max(0, min(WIDTH - 1, self.x + dx))
        self.y = max(0, min(HEIGHT - 1, self.y + dy))

        self.hunger -= 1
        if self.hunger <= 0:
            self.alive = False

        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1

    def eat(self):
        self.hunger += FOOD_EAT_GAIN
