# Three-Mode Reflection Benchmark (OFF vs STUB vs PROVIDER)

## Run Configuration
- seed: 4242
- width: 72
- height: 72
- initial_population: 40
- ticks: 2500
- snapshot_interval: 10
- A: LLM OFF
- B: STUB MODE (LLM ON + force_local_stub)
- C: PROVIDER MODE (LLM ON + provider_with_stub_fallback)

## A. LLM OFF
- population: 48
- avg_hunger_final: 46.65
- villages: 1
- buildings_by_type: {'house': 12, 'storage': 67}
- stored_resources: {'food': 60, 'wood': 68, 'stone': 139}
- under_construction_final: 1
- transport_network_counts: {'logistics_corridor': 130, 'path': 110, 'road': 149}
- construction_deliveries: 71
- blocked_construction: 0
- storage_utilization_avg: 0.016
- internal_transfers: 0
- production_totals: {'total_wood_gathered': 0, 'total_stone_gathered': 0, 'wood_from_lumberyards': 0, 'stone_from_mines': 0, 'direct_wood_gathered': 0, 'direct_stone_gathered': 0}
- blocked_intentions final/mean: 2 / 2.392
- specialists_by_role: {'builder': 1, 'farmer': 3, 'hauler': 28}
- leadership_changes: 0
- proto_culture_summaries(sample): [{'village_uid': 'v-000001', 'cooperation_norm': 0.815, 'work_norm': 0.807, 'exploration_norm': 0.778, 'risk_norm': 0.178, 'dominant_resource_focus': 'food'}]
- reflection_pipeline: {'trigger_detected': 0, 'attempted': 0, 'executed': 0, 'accepted': 0, 'rejected': 0, 'fallback': 0, 'accepted_by_source': {}, 'rejection_reasons': {}, 'fallback_reasons': {}, 'skip_reasons': {}, 'executed_by_reason': {}, 'executed_by_role': {}, 'accepted_executed_ratio': 0.0, 'reflections_per_100_ticks': 0.0}
- construction_realism: {'sites_started_est': 1, 'sites_completed_est': 0, 'avg_completion_ticks_est': None, 'deliveries_per_completed_building_est': None, 'persistent_under_construction': {'final': 1, 'max': 1, 'mean': 1.0, 'longest_nonzero_snapshot_streak': 240, 'nonzero_samples': 240}, 'notes': 'sites_started/sites_completed/avg_completion_ticks are estimated from sampled under_construction trajectory (snapshot-level).'}

## B. STUB MODE
- population: 120
- avg_hunger_final: 82.0
- villages: 1
- buildings_by_type: {'house': 22, 'storage': 87}
- stored_resources: {'food': 211, 'wood': 67, 'stone': 348}
- under_construction_final: 1
- transport_network_counts: {'logistics_corridor': 283, 'path': 93, 'road': 130}
- construction_deliveries: 245
- blocked_construction: 0
- storage_utilization_avg: 0.029
- internal_transfers: 0
- production_totals: {'total_wood_gathered': 0, 'total_stone_gathered': 0, 'wood_from_lumberyards': 0, 'stone_from_mines': 0, 'direct_wood_gathered': 0, 'direct_stone_gathered': 0}
- blocked_intentions final/mean: 0 / 0.163
- specialists_by_role: {'builder': 1, 'farmer': 2, 'hauler': 92}
- leadership_changes: 0
- proto_culture_summaries(sample): [{'village_uid': 'v-000001', 'cooperation_norm': 0.815, 'work_norm': 0.807, 'exploration_norm': 0.757, 'risk_norm': 0.179, 'dominant_resource_focus': 'food'}]
- reflection_pipeline: {'trigger_detected': 408, 'attempted': 408, 'executed': 408, 'accepted': 408, 'rejected': 0, 'fallback': 0, 'accepted_by_source': {'stub': 408}, 'rejection_reasons': {}, 'fallback_reasons': {}, 'skip_reasons': {'brain_interval': 72, 'cooldown': 9424, 'global_budget_exhausted': 963, 'low_relevance': 21001, 'no_trigger_reason': 621}, 'executed_by_reason': {'conflicting_local_needs': 323, 'uncertain_cooperative_choice': 85}, 'executed_by_role': {'npc': 244, 'hauler': 85, 'farmer': 52, 'builder': 26, 'forager': 1}, 'accepted_executed_ratio': 1.0, 'reflections_per_100_ticks': 16.32}
- construction_realism: {'sites_started_est': 3, 'sites_completed_est': 2, 'avg_completion_ticks_est': 1190.0, 'deliveries_per_completed_building_est': 122.5, 'persistent_under_construction': {'final': 1, 'max': 1, 'mean': 0.992, 'longest_nonzero_snapshot_streak': 174, 'nonzero_samples': 238}, 'notes': 'sites_started/sites_completed/avg_completion_ticks are estimated from sampled under_construction trajectory (snapshot-level).'}

## C. PROVIDER MODE
- population: 120
- avg_hunger_final: 82.0
- villages: 1
- buildings_by_type: {'house': 22, 'storage': 87}
- stored_resources: {'food': 211, 'wood': 67, 'stone': 348}
- under_construction_final: 1
- transport_network_counts: {'logistics_corridor': 283, 'path': 93, 'road': 130}
- construction_deliveries: 245
- blocked_construction: 0
- storage_utilization_avg: 0.029
- internal_transfers: 0
- production_totals: {'total_wood_gathered': 0, 'total_stone_gathered': 0, 'wood_from_lumberyards': 0, 'stone_from_mines': 0, 'direct_wood_gathered': 0, 'direct_stone_gathered': 0}
- blocked_intentions final/mean: 0 / 0.163
- specialists_by_role: {'builder': 1, 'farmer': 2, 'hauler': 92}
- leadership_changes: 0
- proto_culture_summaries(sample): [{'village_uid': 'v-000001', 'cooperation_norm': 0.815, 'work_norm': 0.807, 'exploration_norm': 0.757, 'risk_norm': 0.179, 'dominant_resource_focus': 'food'}]
- reflection_pipeline: {'trigger_detected': 408, 'attempted': 408, 'executed': 408, 'accepted': 408, 'rejected': 408, 'fallback': 0, 'accepted_by_source': {'stub': 408}, 'rejection_reasons': {'malformed_output': 408}, 'fallback_reasons': {}, 'skip_reasons': {'brain_interval': 72, 'cooldown': 9424, 'global_budget_exhausted': 963, 'low_relevance': 21001, 'no_trigger_reason': 621}, 'executed_by_reason': {'conflicting_local_needs': 323, 'uncertain_cooperative_choice': 85}, 'executed_by_role': {'npc': 244, 'hauler': 85, 'farmer': 52, 'builder': 26, 'forager': 1}, 'accepted_executed_ratio': 1.0, 'reflections_per_100_ticks': 16.32}
- construction_realism: {'sites_started_est': 3, 'sites_completed_est': 2, 'avg_completion_ticks_est': 1190.0, 'deliveries_per_completed_building_est': 122.5, 'persistent_under_construction': {'final': 1, 'max': 1, 'mean': 0.992, 'longest_nonzero_snapshot_streak': 174, 'nonzero_samples': 238}, 'notes': 'sites_started/sites_completed/avg_completion_ticks are estimated from sampled under_construction trajectory (snapshot-level).'}

## Cross-Mode Highlights
- population: OFF 48 | STUB 120 | PROVIDER 120
- avg_hunger_final: OFF 46.65 | STUB 82.0 | PROVIDER 82.0
- blocked_intentions_mean: OFF 2.392 | STUB 0.163 | PROVIDER 0.163
- accepted/executed ratio: OFF 0.0 | STUB 1.0 | PROVIDER 1.0
- reflections per 100 ticks: OFF 0.0 | STUB 16.32 | PROVIDER 16.32
- accepted_by_source STUB: {'stub': 408}
- accepted_by_source PROVIDER: {'stub': 408}

