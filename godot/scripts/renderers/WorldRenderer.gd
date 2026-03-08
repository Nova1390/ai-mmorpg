extends Node2D
class_name WorldRenderer

var last_state: Dictionary = {}
@onready var _tile_renderer: TileRenderer = $TileRenderer as TileRenderer
@onready var _structure_layer: StructureLayer = $StructureLayer as StructureLayer
@onready var _road_layer: RoadLayer = $RoadLayer as RoadLayer
@onready var _farm_layer: FarmLayer = $FarmLayer as FarmLayer
@onready var _village_renderer: VillageRenderer = $VillageRenderer as VillageRenderer
@onready var _agent_renderer: AgentRenderer = $AgentRenderer as AgentRenderer


func apply_state(state: Dictionary) -> void:
	last_state = state

	if _tile_renderer != null:
		_tile_renderer.apply_state(state)
		_sync_tile_size_from_tile_renderer()

	if _structure_layer != null:
		_structure_layer.apply_state(state)

	if _road_layer != null:
		_road_layer.apply_state(state)

	if _farm_layer != null:
		_farm_layer.apply_state(state)

	if _village_renderer != null:
		_village_renderer.apply_state(state)

	if _agent_renderer != null:
		_agent_renderer.apply_state(state)


func _sync_tile_size_from_tile_renderer() -> void:
	if _tile_renderer == null:
		return

	var size: float = _tile_renderer.tile_size
	if _structure_layer != null:
		_structure_layer.set_tile_size(size)
	if _road_layer != null:
		_road_layer.set_tile_size(size)
	if _farm_layer != null:
		_farm_layer.set_tile_size(size)
	if _village_renderer != null:
		_village_renderer.set_tile_size(size)
	if _agent_renderer != null:
		_agent_renderer.set_tile_size(size)
