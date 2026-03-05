def _norm(text: str) -> str:
    return (text or "").strip().lower()


def plan_from_goal(goal):
    """
    goal può essere dict {"text": "..."} o stringa.
    ritorna lista step.
    """
    if isinstance(goal, dict):
        text = goal.get("text", "")
    else:
        text = str(goal)

    t = _norm(text)

    # GATHER
    if "wood" in t and ("gather" in t or "collect" in t):
        return [
            {"action": "gather", "resource": "wood"},
            {"action": "gather", "resource": "wood"},
            {"action": "gather", "resource": "wood"},
        ]

    if "stone" in t and ("gather" in t or "collect" in t):
        return [
            {"action": "gather", "resource": "stone"},
            {"action": "gather", "resource": "stone"},
            {"action": "gather", "resource": "stone"},
        ]

    if "food" in t and ("gather" in t or "collect" in t or "hunt" in t):
        return [
            {"action": "gather", "resource": "food"},
            {"action": "gather", "resource": "food"},
        ]

    # EXPLORE
    if "explore" in t or "scout" in t or "wander" in t:
        return [{"action": "explore"} for _ in range(10)]

    # RETURN HOME (marker, per ora)
    if "return home" in t or "go home" in t or "back home" in t:
        return [{"action": "return_home"}]

    # BUILD HOUSE (marker: lo implementiamo subito dopo)
    if "build" in t and "house" in t:
        return [
            {"action": "gather", "resource": "wood"},
            {"action": "gather", "resource": "wood"},
            {"action": "gather", "resource": "wood"},
            {"action": "gather", "resource": "wood"},
            {"action": "gather", "resource": "wood"},
            {"action": "gather", "resource": "stone"},
            {"action": "gather", "resource": "stone"},
            {"action": "gather", "resource": "stone"},
            {"action": "build", "what": "house"},
        ]

    # fallback: esplora un po'
    return [{"action": "explore"} for _ in range(5)]


def advance_plan_if_progress(agent, before_inv, after_inv):
    """
    Consuma 1 step quando:
    - gather X: inventory[X] è aumentato nel tick
    - explore/return_home/build: consumati subito (per ora)
    """
    if not agent.current_plan:
        return

    step = agent.current_plan[0]
    action = step.get("action")

    if action == "gather":
        res = step.get("resource")
        if res in before_inv and res in after_inv and after_inv[res] > before_inv[res]:
            agent.current_plan.pop(0)
        return

    if action in ("explore", "return_home", "build"):
        agent.current_plan.pop(0)
        return