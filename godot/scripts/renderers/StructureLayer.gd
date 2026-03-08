extends Node2D
class_name StructureLayer

@export_range(2.0, 128.0, 1.0, "or_greater") var tile_size: float = 16.0

var _structures: Array[Vector2i] = []


func set_tile_size(value: float) -> void:
	var next_size: float = max(2.0, value)
	if is_equal_approx(tile_size, next_size):
		return
	tile_size = next_size
	queue_redraw()


func apply_state(state: Dictionary) -> void:
	var structures_value: Variant = state.get("structures", [])
	if typeof(structures_value) != TYPE_ARRAY:
		if not _structures.is_empty():
			_structures = []
			queue_redraw()
		return

	var next_structures: Array[Vector2i] = []
	for item in (structures_value as Array):
		var point: Variant = _extract_point(item)
		if point != null:
			next_structures.append(point as Vector2i)

	next_structures.sort_custom(_sort_points)
	if next_structures == _structures:
		return

	_structures = next_structures
	queue_redraw()


func _draw() -> void:
	var color: Color = Color(0.78, 0.72, 0.62, 0.85)
	for point in _structures:
		var rect: Rect2 = Rect2(
			Vector2(float(point.x) * tile_size, float(point.y) * tile_size),
			Vector2(tile_size, tile_size)
		)
		draw_rect(rect, color, true)


func _extract_point(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	var data: Dictionary = value as Dictionary
	if not data.has("x") or not data.has("y"):
		return null
	return Vector2i(_to_int(data.get("x", 0)), _to_int(data.get("y", 0)))


func _sort_points(a: Vector2i, b: Vector2i) -> bool:
	if a.y == b.y:
		return a.x < b.x
	return a.y < b.y


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
