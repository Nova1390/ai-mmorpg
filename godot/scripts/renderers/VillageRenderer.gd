extends Node2D
class_name VillageRenderer

@export_range(2.0, 128.0, 1.0, "or_greater") var tile_size: float = 16.0

var _villages: Array[Dictionary] = []


func set_tile_size(value: float) -> void:
	var next_size: float = max(2.0, value)
	if is_equal_approx(tile_size, next_size):
		return
	tile_size = next_size
	queue_redraw()


func apply_state(state: Dictionary) -> void:
	var villages_value: Variant = state.get("villages", [])
	if typeof(villages_value) != TYPE_ARRAY:
		if not _villages.is_empty():
			_villages = []
			queue_redraw()
		return

	var next_villages: Array[Dictionary] = []
	for item in (villages_value as Array):
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var village: Dictionary = item as Dictionary
		var center: Variant = _extract_point(village.get("center", null))
		if center == null:
			continue

		var village_id: String = str(village.get("id", ""))
		var base_color: Color = _resolve_village_color(village.get("color", null), village_id)
		var tiles: Array[Vector2i] = _extract_tiles(village.get("tiles", []))
		var storage_pos: Variant = _extract_point(village.get("storage_pos", null))
		var farm_zone_center: Variant = _extract_point(village.get("farm_zone_center", null))

		next_villages.append({
			"id": village_id,
			"center": center,
			"tiles": tiles,
			"color": base_color,
			"storage_pos": storage_pos,
			"farm_zone_center": farm_zone_center
		})

	next_villages.sort_custom(_sort_villages)
	if next_villages == _villages:
		return

	_villages = next_villages
	queue_redraw()


func _draw() -> void:
	for village in _villages:
		var base_color: Color = village.get("color", Color(0.80, 0.32, 0.22, 1.0))
		var territory: Array[Vector2i] = village.get("tiles", [])
		for cell in territory:
			var rect: Rect2 = Rect2(
				Vector2(float(cell.x) * tile_size, float(cell.y) * tile_size),
				Vector2(tile_size, tile_size)
			)
			draw_rect(rect, Color(base_color.r, base_color.g, base_color.b, 0.17), true)

		var center: Vector2i = village.get("center", Vector2i.ZERO)
		var center_pos: Vector2 = Vector2((float(center.x) + 0.5) * tile_size, (float(center.y) + 0.5) * tile_size)
		var center_radius: float = tile_size * 0.26
		draw_circle(center_pos, center_radius, Color(base_color.r, base_color.g, base_color.b, 0.95))
		draw_arc(center_pos, center_radius, 0.0, TAU, 20, Color(0.08, 0.08, 0.10, 0.95), max(1.0, tile_size * 0.06))

		var storage_pos: Variant = village.get("storage_pos", null)
		if storage_pos != null:
			var storage: Vector2i = storage_pos as Vector2i
			var inset: float = tile_size * 0.30
			var storage_rect: Rect2 = Rect2(
				Vector2(float(storage.x) * tile_size + inset, float(storage.y) * tile_size + inset),
				Vector2(tile_size - 2.0 * inset, tile_size - 2.0 * inset)
			)
			draw_rect(storage_rect, Color(0.98, 0.98, 0.98, 0.95), true)

		var farm_zone_pos: Variant = village.get("farm_zone_center", null)
		if farm_zone_pos != null:
			var farm_center: Vector2i = farm_zone_pos as Vector2i
			var p: Vector2 = Vector2(
				(float(farm_center.x) + 0.5) * tile_size,
				(float(farm_center.y) + 0.5) * tile_size
			)
			var arm: float = tile_size * 0.20
			var width: float = max(1.0, tile_size * 0.06)
			var cross_color: Color = Color(0.14, 0.14, 0.14, 0.88)
			draw_line(p + Vector2(-arm, 0.0), p + Vector2(arm, 0.0), cross_color, width)
			draw_line(p + Vector2(0.0, -arm), p + Vector2(0.0, arm), cross_color, width)


func _extract_tiles(value: Variant) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []
	if typeof(value) != TYPE_ARRAY:
		return tiles

	for item in (value as Array):
		var point: Variant = _extract_point(item)
		if point != null:
			tiles.append(point as Vector2i)

	tiles.sort_custom(_sort_points)
	return tiles


func _extract_point(value: Variant) -> Variant:
	if typeof(value) != TYPE_DICTIONARY:
		return null
	var data: Dictionary = value as Dictionary
	if not data.has("x") or not data.has("y"):
		return null
	return Vector2i(_to_int(data.get("x", 0)), _to_int(data.get("y", 0)))


func _resolve_village_color(color_value: Variant, village_id: String) -> Color:
	if typeof(color_value) == TYPE_STRING:
		var text: String = str(color_value).strip_edges()
		if not text.is_empty():
			var parsed: Color = Color.from_string(text, Color(0.0, 0.0, 0.0, 0.0))
			if parsed.a > 0.0:
				return Color(parsed.r, parsed.g, parsed.b, 1.0)
	return _fallback_color_for_id(village_id)


func _fallback_color_for_id(village_id: String) -> Color:
	var hash_value: int = hash(village_id)
	var hue: float = float(abs(hash_value % 360)) / 360.0
	var color: Color = Color.from_hsv(hue, 0.60, 0.88, 1.0)
	return Color(color.r, color.g, color.b, 1.0)


func _sort_points(a: Vector2i, b: Vector2i) -> bool:
	if a.y == b.y:
		return a.x < b.x
	return a.y < b.y


func _sort_villages(a: Dictionary, b: Dictionary) -> bool:
	var a_id: String = str(a.get("id", ""))
	var b_id: String = str(b.get("id", ""))
	if a_id == b_id:
		var a_center: Vector2i = a.get("center", Vector2i.ZERO)
		var b_center: Vector2i = b.get("center", Vector2i.ZERO)
		if a_center.y == b_center.y:
			return a_center.x < b_center.x
		return a_center.y < b_center.y
	return a_id < b_id


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
