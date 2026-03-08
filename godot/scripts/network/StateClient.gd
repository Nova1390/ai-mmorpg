extends Node
class_name StateClient

signal state_updated(state: Dictionary)
signal state_error(message: String)

@export var endpoint_url: String = "http://127.0.0.1:8000/state"
@export var static_endpoint_url: String = "http://127.0.0.1:8000/state/static"
@export_range(0.05, 60.0, 0.05, "or_greater") var poll_interval: float = 0.2

var _poll_timer: Timer
var _http_request: HTTPRequest
var _static_http_request: HTTPRequest
var _request_in_flight: bool = false
var _static_request_in_flight: bool = false

var _static_width: Variant = null
var _static_height: Variant = null
var _static_tiles: Variant = null
var _static_loaded: bool = false


func _ready() -> void:
	_ensure_http_request()
	_ensure_static_http_request()
	_ensure_poll_timer()
	_fetch_static_state()
	_poll_timer.start()
	_poll_state()


func _ensure_http_request() -> void:
	_http_request = get_node_or_null("StateHttpRequest")
	if _http_request == null:
		_http_request = HTTPRequest.new()
		_http_request.name = "StateHttpRequest"
		add_child(_http_request)

	if not _http_request.request_completed.is_connected(_on_request_completed):
		_http_request.request_completed.connect(_on_request_completed)


func _ensure_static_http_request() -> void:
	_static_http_request = get_node_or_null("StaticStateHttpRequest")
	if _static_http_request == null:
		_static_http_request = HTTPRequest.new()
		_static_http_request.name = "StaticStateHttpRequest"
		add_child(_static_http_request)

	if not _static_http_request.request_completed.is_connected(_on_static_request_completed):
		_static_http_request.request_completed.connect(_on_static_request_completed)


func _ensure_poll_timer() -> void:
	_poll_timer = get_node_or_null("PollTimer")
	if _poll_timer == null:
		_poll_timer = Timer.new()
		_poll_timer.name = "PollTimer"
		add_child(_poll_timer)

	_poll_timer.one_shot = false
	_poll_timer.wait_time = max(0.05, poll_interval)

	if not _poll_timer.timeout.is_connected(_on_poll_timer_timeout):
		_poll_timer.timeout.connect(_on_poll_timer_timeout)


func _on_poll_timer_timeout() -> void:
	_poll_state()


func _fetch_static_state() -> void:
	if _static_request_in_flight or _static_loaded:
		return

	_static_request_in_flight = true
	var err: Error = _static_http_request.request(
		static_endpoint_url,
		PackedStringArray(),
		HTTPClient.METHOD_GET
	)
	if err != OK:
		_static_request_in_flight = false
		state_error.emit("Static state request failed to start (%s)." % error_string(err))


func _poll_state() -> void:
	if _request_in_flight:
		return

	_request_in_flight = true
	var err: Error = _http_request.request(
		endpoint_url,
		PackedStringArray(),
		HTTPClient.METHOD_GET
	)
	if err != OK:
		_request_in_flight = false
		state_error.emit("State request failed to start (%s)." % error_string(err))


func _on_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	_request_in_flight = false

	if result != HTTPRequest.RESULT_SUCCESS:
		state_error.emit("State request transport error (result=%d)." % result)
		return

	if response_code != 200:
		state_error.emit("State endpoint returned HTTP %d." % response_code)
		return

	var body_text: String = body.get_string_from_utf8()
	var json: JSON = JSON.new()
	var parse_err: Error = json.parse(body_text)
	if parse_err != OK:
		state_error.emit(
			"Invalid JSON from state endpoint: %s (line %d)."
			% [json.get_error_message(), json.get_error_line()]
		)
		return

	var parsed: Variant = json.data
	if typeof(parsed) != TYPE_DICTIONARY:
		state_error.emit(
			"Unexpected state payload type: %s."
			% type_string(typeof(parsed))
		)
		return

	var state_dict: Dictionary = parsed as Dictionary
	state_updated.emit(_merge_static_fields(state_dict))


func _on_static_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	_static_request_in_flight = false

	if result != HTTPRequest.RESULT_SUCCESS:
		state_error.emit("Static state request transport error (result=%d)." % result)
		return

	if response_code != 200:
		state_error.emit("Static state endpoint returned HTTP %d." % response_code)
		return

	var body_text: String = body.get_string_from_utf8()
	var json: JSON = JSON.new()
	var parse_err: Error = json.parse(body_text)
	if parse_err != OK:
		state_error.emit(
			"Invalid JSON from static state endpoint: %s (line %d)."
			% [json.get_error_message(), json.get_error_line()]
		)
		return

	var parsed: Variant = json.data
	if typeof(parsed) != TYPE_DICTIONARY:
		state_error.emit(
			"Unexpected static state payload type: %s."
			% type_string(typeof(parsed))
		)
		return

	_store_static_fields(parsed as Dictionary)


func _store_static_fields(static_state: Dictionary) -> void:
	_static_width = static_state.get("width", null)
	_static_height = static_state.get("height", null)

	if static_state.has("tiles"):
		var tiles_value: Variant = static_state.get("tiles", null)
		if typeof(tiles_value) == TYPE_ARRAY:
			_static_tiles = (tiles_value as Array).duplicate(true)
		else:
			_static_tiles = tiles_value
	else:
		_static_tiles = null

	_static_loaded = (
		_static_width != null
		and _static_height != null
		and _static_tiles != null
	)

	if not _static_loaded:
		state_error.emit("Static state loaded, but width/height/tiles are incomplete.")


func _merge_static_fields(dynamic_state: Dictionary) -> Dictionary:
	var merged: Dictionary = dynamic_state.duplicate(true)
	if not _static_loaded:
		return merged

	if not merged.has("width"):
		merged["width"] = _static_width
	if not merged.has("height"):
		merged["height"] = _static_height
	if not merged.has("tiles"):
		merged["tiles"] = _static_tiles

	return merged
