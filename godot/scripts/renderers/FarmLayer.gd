extends Node2D
class_name FarmLayer

@export_range(2.0, 128.0, 1.0, "or_greater") var tile_size: float = 16.0

var _farms: Array[Dictionary] = []


func set_tile_size(value: float) -> void:
	var next_size: float = max(2.0, value)
	if is_equal_approx(tile_size, next_size):
		return
	tile_size = next_size
	queue_redraw()


func apply_state(state: Dictionary) -> void:
	var farms_value: Variant = state.get("farms", [])
	if typeof(farms_value) != TYPE_ARRAY:
		if not _farms.is_empty():
			_farms = []
			queue_redraw()
		return

	var next_farms: Array[Dictionary] = []
	for item in (farms_value as Array):
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var farm: Dictionary = item as Dictionary
		if not farm.has("x") or not farm.has("y"):
			continue

		next_farms.append({
			"x": _to_int(farm.get("x", 0)),
			"y": _to_int(farm.get("y", 0)),
			"state": str(farm.get("state", "unknown"))
		})

	next_farms.sort_custom(_sort_farms)
	if next_farms == _farms:
		return

	_farms = next_farms
	queue_redraw()


func _draw() -> void:
	for farm in _farms:
		var x: int = farm.get("x", 0)
		var y: int = farm.get("y", 0)
		var state: String = farm.get("state", "unknown")
		var rect: Rect2 = Rect2(
			Vector2(float(x) * tile_size, float(y) * tile_size),
			Vector2(tile_size, tile_size)
		)
		draw_rect(rect, _color_for_farm_state(state), true)
		# TODO: Growth-stage detail can be visualized from `growth` in a later iteration.


func _color_for_farm_state(state: String) -> Color:
	match state:
		"prepared":
			return Color(0.56, 0.40, 0.25, 0.70)
		"planted":
			return Color(0.32, 0.58, 0.28, 0.70)
		"growing":
			return Color(0.48, 0.70, 0.30, 0.70)
		"ripe":
			return Color(0.88, 0.78, 0.30, 0.75)
		"dead":
			return Color(0.28, 0.28, 0.28, 0.70)
		_:
			return Color(0.40, 0.50, 0.30, 0.65)


func _sort_farms(a: Dictionary, b: Dictionary) -> bool:
	var ay: int = a.get("y", 0)
	var by: int = b.get("y", 0)
	if ay == by:
		var ax: int = a.get("x", 0)
		var bx: int = b.get("x", 0)
		if ax == bx:
			return str(a.get("state", "")) < str(b.get("state", ""))
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
