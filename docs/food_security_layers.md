# FOOD-SECURITY-001: Life-First Food Security Layers

## Purpose
Separate food behavior into explicit life-first loops so survival and continuity are not modeled as a single undifferentiated task stream.

## Layers
1. `self_feeding`
- Immediate survival loop: acquire/consume food to avoid starvation.
- Typical actions: wild gather + direct eat, inventory eat.

2. `group_feeding`
- Local continuity loop: contribute food to nearby camp/house buffers so the local nucleus remains viable.
- Typical actions: `camp_supply_food`, nearby domestic/camp deposits.

3. `reserve_accumulation`
- Anti-scarcity loop: move food into longer-lived buffers (camp/house/storage) when immediate survival is covered.

4. `reserve_draw`
- Scarcity resilience loop: consume from shared/local reserves during pressure periods.

## Design rules
- Survival-first remains invariant: self-feeding can override all other loops under acute hunger.
- Group and reserve loops are supportive, never absolute; they should not force suicidal donation behavior.
- Reserve is a continuity mechanism, not an early mandatory structure requirement.

## Observability contract (initial)
The simulation now tracks:
- `food_self_feeding_events/units`
- `food_group_feeding_events/units`
- `food_reserve_accumulation_events/units`
- `food_reserve_draw_events/units`
- `food_reserve_balance_units`
- `ratio_food_security_layer_self_feeding`
- `ratio_food_security_layer_group_feeding`
- `ratio_food_security_layer_reserve_accumulation`
- `ratio_food_security_layer_none`
- `food_security_layer_transition_count`
- transition pairs (examples):
  - `food_security_layer_transition_none_to_self_feeding`
  - `food_security_layer_transition_self_feeding_to_group_feeding`
  - `food_security_layer_transition_group_feeding_to_reserve_accumulation`
- reserve activation diagnostics:
  - `food_security_reserve_entry_checks`
  - `food_security_reserve_entry_condition_met_count`
  - `food_security_reserve_entry_activated_count`
  - `food_security_reserve_entry_blocked_*`
- reserve decision-flow diagnostics:
  - `food_security_reserve_prepolicy_candidate_count`
  - `food_security_reserve_postpolicy_candidate_count`
  - `food_security_reserve_final_activation_count`
  - `food_security_reserve_selection_considered_count`
  - `food_security_reserve_selection_chosen_count`
  - `food_security_reserve_selection_rejected_count`
  - `food_security_reserve_selection_rejected_by_group_feeding_count`
  - `food_security_reserve_selection_rejected_by_unstable_context_count`
  - `food_security_reserve_selection_rejected_by_no_surplus_count`
  - `food_security_reserve_selection_rejected_by_other_count`
- reserve final winner/loser diagnostics:
  - `food_security_reserve_final_selection_lost_to_self_feeding_count`
  - `food_security_reserve_final_selection_lost_to_group_feeding_count`
  - `food_security_reserve_final_selection_lost_to_unstable_context_count`
  - `food_security_reserve_final_selection_lost_to_no_surplus_count`
  - `food_security_reserve_final_selection_lost_to_other_count`
  - `food_security_reserve_final_selection_winner_self_feeding_count`
  - `food_security_reserve_final_selection_winner_group_feeding_count`
  - `food_security_reserve_final_selection_winner_other_count`
  - `food_security_reserve_loss_stage_policy_ranking_count`
  - `food_security_reserve_loss_stage_final_gate_count`
  - `food_security_reserve_loss_stage_final_override_count`
- reserve final decision-path diagnostics:
  - `food_security_reserve_final_decision_candidate_count`
  - `food_security_reserve_final_decision_candidate_survived_prepolicy_count`
  - `food_security_reserve_final_decision_candidate_survived_postpolicy_count`
  - `food_security_reserve_final_decision_candidate_lost_count`
  - `food_security_reserve_final_decision_candidate_chosen_count`
  - `food_security_reserve_final_selected_task_*`
  - `food_security_reserve_final_selected_layer_*`
  - `food_security_reserve_final_winner_subsystem_*`
  - `food_security_reserve_final_override_reason_*`
- reserve final tie-break diagnostics:
  - `reserve_final_tiebreak_invoked_count`
  - `reserve_final_tiebreak_won_count`
  - `reserve_final_tiebreak_lost_count`
  - `reserve_final_tiebreak_blocked_by_pressure_count`
  - `reserve_final_tiebreak_blocked_by_unstable_context_count`
  - `reserve_final_tiebreak_blocked_by_no_surplus_count`
- reserve impact diagnostics:
  - `total_food_in_reserves`
  - `avg_food_in_reserves`
  - `max_food_in_reserves`
  - `reserve_fill_events`
  - `reserve_depletion_events`
  - `ticks_reserve_above_threshold`
  - `ticks_reserve_empty`
  - `reserve_recovery_cycles`
  - `hunger_deaths_with_reserve_available`
  - `hunger_deaths_without_reserve`
  - `avg_agent_hunger_when_reserve_used`
  - `reserve_draw_events_during_food_stress`
  - `reserve_draw_events_during_normal_conditions`
  - `average_settlement_food_buffer`
  - `longest_reserve_continuity_window`
  - `settlement_food_shortage_events`
  - `reserve_usage_after_failed_foraging_trip`
- reserve continuity diagnostics (FOOD-SECURITY-011):
  - `reserve_refill_attempts`
  - `reserve_refill_success`
  - `avg_food_added_per_refill`
  - `ticks_between_reserve_refills`
  - `avg_food_draw_per_event`
  - `ticks_between_reserve_draws`
  - `reserve_refill_blocked_by_pressure`
  - `reserve_refill_blocked_by_no_surplus`
  - `reserve_refill_blocked_by_unstable_context`
  - `reserve_partial_recovery_cycles`
  - `reserve_full_recovery_cycles`
  - `reserve_failed_recovery_attempts`
- local survival handoff diagnostics (RESOURCE-EXCHANGE-001):
  - `local_food_handoff_events`
  - `local_food_handoff_units`
  - `handoff_allowed_by_context_count`
  - `handoff_blocked_by_group_priority_count`
  - `handoff_blocked_by_cooldown_count`
  - `handoff_blocked_by_same_unit_recently_count`
  - `handoff_blocked_by_receiver_viability`
  - `handoff_blocked_by_camp_fragility`
  - `handoff_blocked_by_recent_rescue`
  - `local_food_handoff_prevented_by_low_surplus`
  - `local_food_handoff_prevented_by_distance`
  - `local_food_handoff_prevented_by_donor_risk`
  - `hunger_relief_after_local_handoff`

These metrics are descriptive architecture groundwork; they do not imply abundance tuning.
