extends Node2D
class_name AgentRenderer

@export_range(2.0, 128.0, 1.0, "or_greater") var tile_size: float = 16.0

var _agents: Array[Dictionary] = []


func set_tile_size(value: float) -> void:
	var next_size: float = max(2.0, value)
	if is_equal_approx(tile_size, next_size):
		return
	tile_size = next_size
	queue_redraw()


func apply_state(state: Dictionary) -> void:
	var agents_value: Variant = state.get("agents", [])
	if typeof(agents_value) != TYPE_ARRAY:
		if not _agents.is_empty():
			_agents = []
			queue_redraw()
		return

	var next_agents: Array[Dictionary] = []
	for item in (agents_value as Array):
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var data: Dictionary = item as Dictionary
		if not data.has("x") or not data.has("y"):
			continue

		next_agents.append({
			"x": _to_int(data.get("x", 0)),
			"y": _to_int(data.get("y", 0)),
			"role": str(data.get("role", "npc")).to_lower(),
			"is_player": _to_bool(data.get("is_player", false)),
			"player_id": str(data.get("player_id", "")),
			"village_id": str(data.get("village_id", "")),
			"task": str(data.get("task", ""))
		})

	next_agents.sort_custom(_sort_agents)
	if next_agents == _agents:
		return

	_agents = next_agents
	queue_redraw()


func _draw() -> void:
	# TODO: Add smooth tracked motion only after stable unique agent IDs are present in the contract.
	for agent in _agents:
		var x: int = agent.get("x", 0)
		var y: int = agent.get("y", 0)
		var role: String = agent.get("role", "npc")
		var is_player: bool = agent.get("is_player", false)

		var center: Vector2 = Vector2(
			(float(x) + 0.5) * tile_size,
			(float(y) + 0.5) * tile_size
		)
		var radius: float = tile_size * 0.24
		if role == "leader":
			radius = tile_size * 0.28
		if is_player:
			radius += tile_size * 0.04

		var fill_color: Color = _color_for_role(role, is_player)
		draw_circle(center, radius, fill_color)

		var outline_width: float = max(1.0, tile_size * 0.06)
		var outline_color: Color = Color(0.10, 0.10, 0.12, 0.95)
		if is_player:
			outline_color = Color(0.95, 0.95, 0.95, 0.95)
		elif role == "leader":
			outline_color = Color(0.96, 0.88, 0.28, 0.95)
		draw_arc(center, radius, 0.0, TAU, 16, outline_color, outline_width)


func _color_for_role(role: String, is_player: bool) -> Color:
	if is_player:
		return Color(0.25, 0.78, 0.95, 1.0)

	match role:
		"leader":
			return Color(0.93, 0.72, 0.16, 1.0)
		"farmer":
			return Color(0.42, 0.74, 0.30, 1.0)
		"builder":
			return Color(0.82, 0.56, 0.27, 1.0)
		"hauler":
			return Color(0.74, 0.46, 0.88, 1.0)
		"forager":
			return Color(0.26, 0.63, 0.58, 1.0)
		_:
			return Color(0.82, 0.82, 0.86, 1.0)


func _sort_agents(a: Dictionary, b: Dictionary) -> bool:
	var ay: int = a.get("y", 0)
	var by: int = b.get("y", 0)
	if ay == by:
		var ax: int = a.get("x", 0)
		var bx: int = b.get("x", 0)
		if ax == bx:
			return str(a.get("role", "")) < str(b.get("role", ""))
		return ax < bx
	return ay < by


func _to_int(value: Variant) -> int:
	match typeof(value):
		TYPE_INT:
			return value
		TYPE_FLOAT:
			return int(value)
		TYPE_BOOL:
			return int(value)
		TYPE_STRING:
			if value.is_valid_int():
				return value.to_int()
			if value.is_valid_float():
				return int(value.to_float())
			return 0
		_:
			return 0


func _to_bool(value: Variant) -> bool:
	match typeof(value):
		TYPE_BOOL:
			return value
		TYPE_INT:
			return value != 0
		TYPE_FLOAT:
			return not is_zero_approx(value)
		TYPE_STRING:
			var text: String = value.to_lower()
			return text == "true" or text == "1" or text == "yes"
		_:
			return false
