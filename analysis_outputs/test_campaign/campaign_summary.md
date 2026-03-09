# Global Multi-Scenario Test Campaign Summary

## Configuration
- Scenario A (GENERAL BASELINE): seed=4242, map=72x72, pop=40, ticks=2500
- Scenario B (LOGISTICS / CONSTRUCTION STRESS): seed=4343, map=96x96, pop=48, ticks=2400
- Scenario C (SPECIALIZATION / PRODUCTION STRESS): seed=4444, map=72x72, pop=44, ticks=2400
- Scenario D (INNOVATION STRESS): seed=4545, map=72x72, pop=40, ticks=2800
- Modes: OFF, STUB (force_local_stub)

## Per-Scenario Results (OFF vs STUB)
### Scenario A – GENERAL BASELINE
- Population: OFF 37 | STUB 40
- Avg hunger: OFF 34.68 | STUB 33.67
- Food crisis count: OFF 0 | STUB 0
- Stored food/wood/stone: OFF 32/5/60 | STUB 30/53/54
- Total gathered F/W/S: OFF 744/138/117 | STUB 658/126/69
- Specialization ratios (wood, stone): OFF 0.000, 0.000 | STUB 0.000, 0.000
- Logistics deliveries/internal transfers/blocked: OFF 0/0/0 | STUB 0/0/0
- Reflection attempts per 100 ticks: OFF 0.00 | STUB 5.16
- Innovation proposals/admissible/prototype built/useful: OFF 0/0/0/0 | STUB 0/0/0/0

### Scenario B – LOGISTICS / CONSTRUCTION STRESS
- Population: OFF 7 | STUB 6
- Avg hunger: OFF 38.86 | STUB 28.67
- Food crisis count: OFF 0 | STUB 0
- Stored food/wood/stone: OFF 5/0/0 | STUB 5/0/0
- Total gathered F/W/S: OFF 320/84/89 | STUB 326/111/111
- Specialization ratios (wood, stone): OFF 0.000, 0.000 | STUB 0.000, 0.000
- Logistics deliveries/internal transfers/blocked: OFF 0/0/0 | STUB 0/0/0
- Reflection attempts per 100 ticks: OFF 0.00 | STUB 0.88
- Innovation proposals/admissible/prototype built/useful: OFF 0/0/0/0 | STUB 0/0/0/0

### Scenario C – SPECIALIZATION / PRODUCTION STRESS
- Population: OFF 35 | STUB 53
- Avg hunger: OFF 34.34 | STUB 67.19
- Food crisis count: OFF 0 | STUB 0
- Stored food/wood/stone: OFF 37/80/210 | STUB 59/101/349
- Total gathered F/W/S: OFF 724/146/277 | STUB 934/156/453
- Specialization ratios (wood, stone): OFF 0.000, 0.000 | STUB 0.000, 0.000
- Logistics deliveries/internal transfers/blocked: OFF 0/0/0 | STUB 7/0/0
- Reflection attempts per 100 ticks: OFF 0.00 | STUB 7.29
- Innovation proposals/admissible/prototype built/useful: OFF 0/0/0/0 | STUB 0/0/0/0

### Scenario D – INNOVATION STRESS
- Population: OFF 103 | STUB 120
- Avg hunger: OFF 83.48 | STUB 84.33
- Food crisis count: OFF 0 | STUB 0
- Stored food/wood/stone: OFF 410/43/6 | STUB 361/83/36
- Total gathered F/W/S: OFF 1579/540/108 | STUB 2319/578/222
- Specialization ratios (wood, stone): OFF 0.000, 0.000 | STUB 0.000, 0.000
- Logistics deliveries/internal transfers/blocked: OFF 0/0/0 | STUB 3/0/0
- Reflection attempts per 100 ticks: OFF 0.00 | STUB 70.18
- Innovation proposals/admissible/prototype built/useful: OFF 0/0/0/0 | STUB 1/1/1/0

## Cross-Scenario Findings
- Activation counts (8 runs): {'world_survival_dynamics': 8, 'reflection_pipeline': 4, 'construction_delivery': 2, 'specialized_production': 0, 'innovation_pipeline': 1, 'invention_knowledge_diffusion': 0}
- which_systems_activate_reliably_in_baseline: Baseline activates survival, village persistence, production totals; does not reliably activate logistics throughput, specialization, or innovation.
- which_systems_only_activate_under_stress: Construction delivery appears only in stress runs (C/D stub); innovation appears only in D stub and remains very limited.
- are_logistics_and_construction_working_at_scale: Partially. Construction deliveries are sparse (0-7 in 2400-2800 ticks) and internal transfers stay 0 across all runs.
- is_specialization_emerging: No. wood_specialization_ratio and stone_specialization_ratio remain 0.0 in all runs.
- is_innovation_emerging: Barely. Only D stub produced 1 admissible proposal -> 1 built prototype, with no useful/neutral/ineffective conclusion and no knowledge spread.
- is_reflection_helping_or_noise: Stub reflection correlates with higher population/storage in C/D and slight gain in A, but also very high call volume (up to 1965 attempts in D stub) with low innovation activation.

## Top 3 Bottlenecks
- Specialization path is not activating (ratios remain 0.0 in all scenarios/modes).
- Logistics throughput is weak at campaign scale (construction deliveries low, internal transfers 0 throughout).
- Innovation chain is rarely triggered and diffusion remains inactive (no known invention entries in all runs).