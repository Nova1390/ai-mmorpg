extends Node2D
class_name MainController

@export var pan_speed: float = 600.0
@export var zoom_step: float = 0.10
@export var min_zoom: float = 0.25
@export var max_zoom: float = 4.0

var last_state: Dictionary = {}
var _auto_fit_done: bool = false
var _is_drag_panning: bool = false

@onready var _state_client: StateClient = $StateClient as StateClient
@onready var _world_renderer: WorldRenderer = $WorldRenderer as WorldRenderer
@onready var _ui_overlay: DebugOverlay = $UIOverlay as DebugOverlay
@onready var _camera: Camera2D = $Camera2D as Camera2D


func _ready() -> void:
	if _camera != null:
		_camera.enabled = true

	if _state_client == null:
		push_warning("StateClient node is missing; observer wiring is disabled.")
		return

	_state_client.state_updated.connect(_on_state_updated)
	_state_client.state_error.connect(_on_state_error)


func _process(delta: float) -> void:
	if _camera == null:
		return

	var direction: Vector2 = Vector2(
		Input.get_axis("ui_left", "ui_right"),
		Input.get_axis("ui_up", "ui_down")
	)
	if direction == Vector2.ZERO:
		return

	var speed_scale: float = max(0.1, _camera.zoom.x)
	_camera.position += direction.normalized() * pan_speed * speed_scale * delta


func _unhandled_input(event: InputEvent) -> void:
	if _camera == null:
		return

	if event is InputEventMouseButton:
		var mouse_event: InputEventMouseButton = event
		if mouse_event.button_index == MOUSE_BUTTON_WHEEL_UP and mouse_event.pressed:
			_apply_zoom(1.0 - zoom_step)
			get_viewport().set_input_as_handled()
			return
		if mouse_event.button_index == MOUSE_BUTTON_WHEEL_DOWN and mouse_event.pressed:
			_apply_zoom(1.0 + zoom_step)
			get_viewport().set_input_as_handled()
			return
		if mouse_event.button_index == MOUSE_BUTTON_MIDDLE:
			_is_drag_panning = mouse_event.pressed
			get_viewport().set_input_as_handled()
			return

	if event is InputEventMouseMotion and _is_drag_panning:
		var motion: InputEventMouseMotion = event
		var zoom_scale: float = max(0.1, _camera.zoom.x)
		_camera.position -= motion.relative * zoom_scale
		get_viewport().set_input_as_handled()


func _on_state_updated(state: Dictionary) -> void:
	last_state = state

	if _world_renderer != null:
		_world_renderer.apply_state(state)

	if _ui_overlay != null:
		_ui_overlay.apply_state(state)

	_try_auto_fit_camera_once(state)


func _on_state_error(message: String) -> void:
	if _ui_overlay != null:
		_ui_overlay.show_error(message)


func _apply_zoom(multiplier: float) -> void:
	var current: float = _camera.zoom.x
	var next: float = clamp(current * multiplier, min_zoom, max_zoom)
	_camera.zoom = Vector2(next, next)


func _try_auto_fit_camera_once(state: Dictionary) -> void:
	if _auto_fit_done or _camera == null:
		return

	var width: int = _to_int(state.get("width", 0))
	var height: int = _to_int(state.get("height", 0))
	if width <= 0 or height <= 0:
		return

	var tile_size: float = _get_tile_size()
	var world_size: Vector2 = Vector2(float(width) * tile_size, float(height) * tile_size)
	if world_size.x <= 0.0 or world_size.y <= 0.0:
		return

	var viewport_size: Vector2 = get_viewport_rect().size
	if viewport_size.x <= 0.0 or viewport_size.y <= 0.0:
		return

	var zoom_fit_x: float = world_size.x / viewport_size.x
	var zoom_fit_y: float = world_size.y / viewport_size.y
	var zoom_fit: float = max(zoom_fit_x, zoom_fit_y)
	if zoom_fit < 1.0:
		zoom_fit = 1.0

	var clamped_zoom: float = clamp(zoom_fit, min_zoom, max_zoom)
	_camera.zoom = Vector2(clamped_zoom, clamped_zoom)
	_camera.position = world_size * 0.5
	_auto_fit_done = true


func _get_tile_size() -> float:
	if _world_renderer == null:
		return 16.0
	var tile_renderer: TileRenderer = _world_renderer.get_node_or_null("TileRenderer") as TileRenderer
	if tile_renderer == null:
		return 16.0
	return max(2.0, tile_renderer.tile_size)


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
