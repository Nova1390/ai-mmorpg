# Baseline Comparison (Post-Fix): LLM OFF vs LLM ON

## Run Configuration
- seed: 4242
- width: 72
- height: 72
- initial_population: 40
- ticks: 2500
- snapshot_interval: 10
- Run A: LLM OFF
- Run B: LLM ON

## Reflection Pipeline
### OFF
- trigger_detected: 0
- attempted: 0
- executed: 0
- accepted: 0
- rejected: 0
- fallback: 0
- executed_by_reason: {}
- executed_by_role: {}
- skip_reasons: {}
### ON
- trigger_detected: 197
- attempted: 197
- executed: 197
- accepted: 0
- rejected: 197
- fallback: 0
- executed_by_reason: {'conflicting_local_needs': 152, 'uncertain_cooperative_choice': 44, 'repeated_local_failure': 1}
- executed_by_role: {'npc': 87, 'farmer': 47, 'hauler': 40, 'builder': 22, 'forager': 1}
- skip_reasons: {'low_relevance': 13858, 'cooldown': 4302, 'no_trigger_reason': 443, 'global_budget_exhausted': 411, 'brain_interval': 72}

## Construction Realism
### OFF
- under_construction final/max: 1 / 1
- longest consecutive non-zero under-construction streak (snapshot steps): 240
- blocked construction count: 0
- construction deliveries count: 71
- completed buildings by type (observed window 110..2500): {'house': 5, 'storage': 64}
### ON
- under_construction final/max: 1 / 1
- longest consecutive non-zero under-construction streak (snapshot steps): 240
- blocked construction count: 0
- construction deliveries count: 366
- completed buildings by type (observed window 110..2500): {'house': 9, 'storage': 83}

## World / Economy / Logistics
- population (OFF -> ON): 48 -> 110
- avg hunger final (OFF -> ON): 46.65 -> 67.59
- storage food (OFF -> ON): 60 -> 132
- storage wood (OFF -> ON): 68 -> 56
- storage stone (OFF -> ON): 139 -> 228
- internal transfers (OFF -> ON): 0 -> 0
- production total wood (OFF -> ON): 0 -> 0
- production total stone (OFF -> ON): 0 -> 0
- specialized wood_from_lumberyards (OFF -> ON): 0 -> 0
- specialized stone_from_mines (OFF -> ON): 0 -> 0
- direct wood (OFF -> ON): 0 -> 0
- direct stone (OFF -> ON): 0 -> 0

## Cognition / Society
- blocked intentions (OFF -> ON): 2 -> 0
- specialists by role OFF: {'builder': 1, 'farmer': 3, 'hauler': 28}
- specialists by role ON: {'builder': 1, 'farmer': 3, 'hauler': 58}
- leadership changes (OFF -> ON): 0 -> 0
- top leaders OFF: [{'agent_id': 'a-000002', 'role': 'hauler', 'social_influence': 0.963}, {'agent_id': 'a-000009', 'role': 'npc', 'social_influence': 0.963}, {'agent_id': 'a-000027', 'role': 'hauler', 'social_influence': 0.962}]
- top leaders ON: [{'agent_id': 'a-000020', 'role': 'npc', 'social_influence': 0.93}, {'agent_id': 'a-000041', 'role': 'npc', 'social_influence': 0.928}, {'agent_id': 'a-000005', 'role': 'npc', 'social_influence': 0.92}]
- proto-culture OFF (sample): [{'village_uid': 'v-000001', 'cooperation_norm': 0.815, 'work_norm': 0.807, 'exploration_norm': 0.778, 'risk_norm': 0.178, 'dominant_resource_focus': 'food'}]
- proto-culture ON (sample): [{'village_uid': 'v-000001', 'cooperation_norm': 0.815, 'work_norm': 0.807, 'exploration_norm': 0.778, 'risk_norm': 0.178, 'dominant_resource_focus': 'food'}]
