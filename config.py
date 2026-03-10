# -------------------------
# MAPPA
# -------------------------
WIDTH = 100
HEIGHT = 100

# Probabilità biomi
P_GRASS = 0.55
P_FOREST = 0.25
P_MOUNTAIN = 0.15
P_WATER = 0.05

# -------------------------
# SIMULAZIONE
# -------------------------
NUM_AGENTS = 0   # NPC spawnati da server.py
TICK_SPEED = 0.5

# limite massimo popolazione totale
MAX_AGENTS = 200

# -------------------------
# RISORSE
# -------------------------
NUM_FOOD = 80
NUM_WOOD = 20
NUM_STONE = 15

FOOD_RESPAWN_PER_TICK = 4
WOOD_RESPAWN_PER_TICK = 1
STONE_RESPAWN_PER_TICK = 1

MAX_FOOD = 200
MAX_WOOD = 120
MAX_STONE = 90

# -------------------------
# SURVIVAL
# -------------------------
AGENT_START_HUNGER = 85
FOOD_EAT_GAIN = 35

# -------------------------
# RIPRODUZIONE NPC
# -------------------------
REPRO_MIN_HUNGER = 90
REPRO_PROB = 0.01
REPRO_COST = 25

# -------------------------
# COSTRUZIONE
# -------------------------
HOUSE_WOOD_COST = 5
HOUSE_STONE_COST = 3

# -------------------------
# VILLAGGI
# -------------------------
NUM_VILLAGES_MIN = 2
NUM_VILLAGES_MAX = 4
VILLAGE_RADIUS = 4
VILLAGE_HOUSES_MIN = 6
VILLAGE_HOUSES_MAX = 12

# -------------------------
# LLM
# -------------------------
LLM_ENABLED = True
LLM_TIMEOUT_SECONDS = 3.0
