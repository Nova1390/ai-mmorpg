# Benchmark2 Three-Mode Comparison (Post Survival Tuning + Production Metrics Fix)

## Run Configuration
- seed: 4242
- width: 72
- height: 72
- initial_population: 40
- ticks: 2500
- snapshot_interval: 10
- A: LLM OFF
- B: LLM ON + force_local_stub
- C: LLM ON + provider_with_stub_fallback

## A. LLM OFF
- survival: population=37 avg_hunger_final=34.68 stored_food_final=32
- avg_hunger_trend(start/mid/end/delta): 63.71 / 42.68 / 34.68 / -29.03
- survival_pressure_avg final/mean: 0.276 / 0.296
- food_crisis_count final/mean: 0 / 3.296
- production: food(total/direct)=744/744 wood(total/direct/spec)=138/138/0 stone(total/direct/spec)=117/117/0
- specialization ratios: wood=0.0 stone=0.0 food_direct=1.0
- logistics: deliveries=0 internal_transfers=0 blocked=0 storage_utilization_avg=0.005
- under_construction final/max/mean: 1 / 1 / 1.0
- buildings_final: {'farm_plot': 48, 'house': 14, 'storage': 71}
- buildings_completed_est(delta from first snapshot): {'farm_plot': 48, 'house': 6, 'storage': 69}
- transport_network_counts: {'logistics_corridor': 175, 'path': 66, 'road': 154}
- reflection: trigger=0 attempted=0 executed=0 accepted=0 rejected=0 fallback=0
- reflection source/reasons: accepted_by_source={} rejection_reasons={} skip_reasons={}
- survival reflection controls: suppressed=0 biased_applied=0
- reflection efficiency: accepted_executed_ratio=0.0 reflections_per_100_ticks=0.0

## B. STUB MODE
- survival: population=40 avg_hunger_final=33.67 stored_food_final=30
- avg_hunger_trend(start/mid/end/delta): 64.81 / 42.69 / 33.67 / -31.14
- survival_pressure_avg final/mean: 0.362 / 0.291
- food_crisis_count final/mean: 0 / 1.65
- production: food(total/direct)=658/658 wood(total/direct/spec)=126/126/0 stone(total/direct/spec)=69/69/0
- specialization ratios: wood=0.0 stone=0.0 food_direct=1.0
- logistics: deliveries=0 internal_transfers=0 blocked=0 storage_utilization_avg=0.007
- under_construction final/max/mean: 0 / 0 / 0.0
- buildings_final: {'house': 11, 'storage': 77}
- buildings_completed_est(delta from first snapshot): {'house': 3, 'storage': 75}
- transport_network_counts: {'logistics_corridor': 116, 'path': 78, 'road': 120}
- reflection: trigger=129 attempted=129 executed=129 accepted=129 rejected=0 fallback=0
- reflection source/reasons: accepted_by_source={'stub': 129} rejection_reasons={} skip_reasons={'low_relevance': 10510, 'brain_interval': 72, 'no_trigger_reason': 183, 'global_budget_exhausted': 463, 'cooldown': 4281}
- survival reflection controls: suppressed=0 biased_applied=0
- reflection efficiency: accepted_executed_ratio=1.0 reflections_per_100_ticks=5.16

## C. PROVIDER+STUB_FALLBACK
- survival: population=40 avg_hunger_final=33.67 stored_food_final=30
- avg_hunger_trend(start/mid/end/delta): 64.81 / 42.69 / 33.67 / -31.14
- survival_pressure_avg final/mean: 0.362 / 0.291
- food_crisis_count final/mean: 0 / 1.65
- production: food(total/direct)=658/658 wood(total/direct/spec)=126/126/0 stone(total/direct/spec)=69/69/0
- specialization ratios: wood=0.0 stone=0.0 food_direct=1.0
- logistics: deliveries=0 internal_transfers=0 blocked=0 storage_utilization_avg=0.007
- under_construction final/max/mean: 0 / 0 / 0.0
- buildings_final: {'house': 11, 'storage': 77}
- buildings_completed_est(delta from first snapshot): {'house': 3, 'storage': 75}
- transport_network_counts: {'logistics_corridor': 116, 'path': 78, 'road': 120}
- reflection: trigger=129 attempted=129 executed=129 accepted=129 rejected=129 fallback=0
- reflection source/reasons: accepted_by_source={'stub': 129} rejection_reasons={'malformed_output': 129} skip_reasons={'low_relevance': 10510, 'brain_interval': 72, 'no_trigger_reason': 183, 'global_budget_exhausted': 463, 'cooldown': 4281}
- survival reflection controls: suppressed=0 biased_applied=0
- reflection efficiency: accepted_executed_ratio=1.0 reflections_per_100_ticks=5.16

## Cross-Mode Highlights
- population_gain_vs_off: {'stub': 3, 'provider': 3}
- avg_hunger_final_delta_vs_off: {'stub': -1.01, 'provider': -1.01}
- stored_food_delta_vs_off: {'stub': -2, 'provider': -2}
- construction_deliveries_delta_vs_off: {'stub': 0, 'provider': 0}
- provider_effectively_stub_replaced: True
