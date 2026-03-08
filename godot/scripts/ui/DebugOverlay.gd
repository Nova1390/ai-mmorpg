extends CanvasLayer
class_name DebugOverlay

var _label: Label
var _last_state: Dictionary = {}
var _last_error: String = ""
var _connection_status: String = "waiting"


func _ready() -> void:
	_label = Label.new()
	_label.name = "MetricsLabel"
	_label.anchor_left = 0.0
	_label.anchor_top = 0.0
	_label.anchor_right = 0.0
	_label.anchor_bottom = 0.0
	_label.offset_left = 12.0
	_label.offset_top = 12.0
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	add_child(_label)
	_refresh_text()


func apply_state(state: Dictionary) -> void:
	_last_state = state
	_connection_status = "connected"
	_refresh_text()


func show_error(message: String) -> void:
	_last_error = message
	_connection_status = "error"
	_refresh_text()


func _refresh_text() -> void:
	var tick: int = _to_int(_last_state.get("tick", 0))
	var population: int = _to_int(_last_state.get("population", 0))
	var villages_count: int = _to_int(_last_state.get("villages_count", 0))
	var leaders_count: int = _to_int(_last_state.get("leaders_count", 0))
	var food_count: int = _to_int(_last_state.get("food_count", 0))
	var wood_count: int = _to_int(_last_state.get("wood_count", 0))
	var stone_count: int = _to_int(_last_state.get("stone_count", 0))
	var map_width: int = _to_int(_last_state.get("width", 0))
	var map_height: int = _to_int(_last_state.get("height", 0))

	var lines: PackedStringArray = [
		"Observer Metrics",
		"status: %s" % _connection_status,
		"tick: %d" % tick,
		"map: %dx%d" % [map_width, map_height],
		"population: %d" % population,
		"villages_count: %d" % villages_count,
		"leaders_count: %d" % leaders_count,
		"food_count: %d" % food_count,
		"wood_count: %d" % wood_count,
		"stone_count: %d" % stone_count,
	]

	if _last_error.is_empty():
		lines.append("error: none")
	else:
		lines.append("error: %s" % _last_error)

	_label.text = "\n".join(lines)


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
