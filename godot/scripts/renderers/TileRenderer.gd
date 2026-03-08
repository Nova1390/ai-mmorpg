extends Node2D
class_name TileRenderer

@export_range(2.0, 128.0, 1.0, "or_greater") var tile_size: float = 16.0

var _map_width: int = 0
var _map_height: int = 0
var _tiles: Array = []
var _has_valid_map: bool = false


func apply_state(state: Dictionary) -> void:
	var has_width: bool = state.has("width")
	var has_height: bool = state.has("height")
	var has_tiles: bool = state.has("tiles")
	if not has_width or not has_height or not has_tiles:
		if _has_valid_map:
			_clear_map()
			queue_redraw()
		return

	var width_value: Variant = state.get("width", 0)
	var height_value: Variant = state.get("height", 0)
	var tiles_value: Variant = state.get("tiles", [])

	if typeof(tiles_value) != TYPE_ARRAY:
		if _has_valid_map:
			_clear_map()
			queue_redraw()
		return

	var next_width: int = _to_int(width_value)
	var next_height: int = _to_int(height_value)
	var next_tiles: Array = (tiles_value as Array).duplicate(true)

	if next_width <= 0:
		next_width = _estimate_width_from_tiles(next_tiles)
	if next_height <= 0:
		next_height = next_tiles.size()

	next_width = max(0, next_width)
	next_height = max(0, next_height)

	var unchanged: bool = (
		_has_valid_map
		and next_width == _map_width
		and next_height == _map_height
		and next_tiles == _tiles
	)
	if unchanged:
		return

	_map_width = next_width
	_map_height = next_height
	_tiles = next_tiles
	_has_valid_map = true
	queue_redraw()


func _draw() -> void:
	if not _has_valid_map:
		return

	for y in range(_map_height):
		if y < 0 or y >= _tiles.size():
			continue
		var row_variant: Variant = _tiles[y]
		if typeof(row_variant) != TYPE_ARRAY:
			continue

		var row: Array = row_variant as Array
		var max_x: int = min(_map_width, row.size())
		for x in range(max_x):
			var code: String = str(row[x])
			var color: Color = _color_for_tile_code(code)
			var rect: Rect2 = Rect2(
				Vector2(float(x) * tile_size, float(y) * tile_size),
				Vector2(tile_size, tile_size)
			)
			draw_rect(rect, color, true)


func _color_for_tile_code(code: String) -> Color:
	match code:
		"G":
			return Color(0.42, 0.68, 0.36, 1.0)
		"F":
			return Color(0.20, 0.45, 0.20, 1.0)
		"M":
			return Color(0.50, 0.52, 0.55, 1.0)
		"W":
			return Color(0.20, 0.43, 0.75, 1.0)
		"H":
			# TODO: Houses/structures should be rendered by a dedicated structure layer.
			return Color(0.72, 0.58, 0.40, 1.0)
		_:
			return Color(0.25, 0.25, 0.25, 1.0)


func _estimate_width_from_tiles(tiles: Array) -> int:
	if tiles.is_empty():
		return 0
	var first_row: Variant = tiles[0]
	if typeof(first_row) != TYPE_ARRAY:
		return 0
	return (first_row as Array).size()


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


func _clear_map() -> void:
	_map_width = 0
	_map_height = 0
	_tiles = []
	_has_valid_map = false
