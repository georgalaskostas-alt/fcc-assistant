from app.dashboard_constraints import conflicts_with_current_turn, explicit_action_families


def _widgets():
    return [{"id": "fcc-feed", "type": "trend", "unit_key": "fcc"}, {"id": "hcu-feed", "type": "trend", "unit_key": "hcu"}]


def test_restore_and_separate_add_are_both_detected():
    assert explicit_action_families("Ξαναβάλε το FCC feed και πρόσθεσε feed στο HCU") == {"restore", "add"}


def test_restore_phrase_does_not_create_fake_add():
    assert explicit_action_families("Βάλε τα πάλι πίσω") == {"restore"}


def test_explicit_action_cannot_compile_to_empty_plan():
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC", {"action": "answer", "read_only": True}, {"fcc"}, _widgets())


def test_non_mutating_answer_with_unit_name_is_allowed():
    assert conflicts_with_current_turn("Τι βλέπω τώρα στο FCC;", {"action": "answer", "read_only": True}, {"fcc"}, _widgets()) == []


def test_explicit_unit_requires_resolvable_target_for_mutating_plan():
    assert conflicts_with_current_turn("Βάλε feed στο FCC", {"action": "add_widget", "widget": {"id": "mystery", "type": "trend"}}, {"fcc"}, _widgets())


def test_wrong_unit_in_compound_transaction_is_rejected():
    plan = {"action": "transaction", "steps": [{"action": "remove_widget", "target_id": "fcc-feed"}, {"action": "add_widget", "widget": {"id": "wrong", "unit_key": "other"}}]}
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC και βάλε feed στο HCU", plan, {"fcc", "hcu"}, _widgets())


def test_compound_remove_and_add_rejects_partial_remove_only_plan():
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC και βάλε feed στο HCU", {"action": "remove_widget", "target_id": "fcc-feed"}, {"fcc", "hcu"}, _widgets())


def test_compound_remove_and_add_rejects_partial_add_only_plan():
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC και βάλε feed στο HCU", {"action": "add_widget", "widget": {"id": "hcu-new", "unit_key": "hcu"}}, {"fcc", "hcu"}, _widgets())


def test_compound_remove_and_add_accepts_complete_transaction():
    plan = {"action": "transaction", "steps": [{"action": "remove_widget", "target_id": "fcc-feed"}, {"action": "add_widget", "widget": {"id": "hcu-new", "unit_key": "hcu"}}]}
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC και βάλε feed στο HCU", plan, {"fcc", "hcu"}, _widgets()) == []


def test_compound_restore_and_add_accepts_two_add_execution_steps():
    plan = {"action": "transaction", "steps": [{"action": "add_widgets", "widgets": [{"id": "fcc-feed-restored", "unit_key": "fcc"}]}, {"action": "add_widget", "widget": {"id": "hcu-new", "unit_key": "hcu"}}]}
    assert conflicts_with_current_turn("Ξαναβάλε το FCC feed και πρόσθεσε feed στο HCU", plan, {"fcc", "hcu"}, _widgets()) == []


def test_english_compound_action_is_detected():
    assert explicit_action_families("Remove the FCC feed and add the HCU feed") == {"remove", "add"}


def test_greek_remove_synonym_vgale_is_detected():
    assert explicit_action_families("Βγάλε το feed από το FCC") == {"remove"}


def test_restore_with_remove_preserves_both_requested_families():
    assert explicit_action_families("Βάλε τα πάλι πίσω και αφαίρεσε το HCU feed") == {"restore", "remove"}


def test_restore_and_remove_rejects_restore_only_execution():
    assert conflicts_with_current_turn("Βάλε τα πάλι πίσω και αφαίρεσε το HCU feed", {"action": "add_widgets", "widgets": [{"id": "fcc-restored", "unit_key": "fcc"}]}, {"fcc", "hcu"}, _widgets())


def test_restore_and_remove_accepts_complete_execution():
    plan = {"action": "transaction", "steps": [{"action": "add_widgets", "widgets": [{"id": "fcc-restored", "unit_key": "fcc"}]}, {"action": "remove_widget", "target_id": "hcu-feed"}]}
    assert conflicts_with_current_turn("Βάλε τα πάλι πίσω και αφαίρεσε το HCU feed", plan, {"fcc", "hcu"}, _widgets()) == []


def test_explicit_fcc_command_rejects_hcu_target_even_with_correct_action():
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC", {"action": "remove_widget", "target_id": "hcu-feed"}, {"fcc"}, _widgets())


def test_no_explicit_unit_allows_context_resolved_unit_target():
    assert conflicts_with_current_turn("Αφαίρεσε αυτό", {"action": "remove_widget", "target_id": "hcu-feed"}, set(), _widgets()) == []


def test_explicit_unit_accepts_matching_context_resolved_target():
    assert conflicts_with_current_turn("Αφαίρεσε αυτό από το FCC", {"action": "remove_widget", "target_id": "fcc-feed"}, {"fcc"}, _widgets()) == []


def test_replace_request_rejects_add_plan():
    assert conflicts_with_current_turn("Αντικατάστησε το FCC feed", {"action": "add_widget", "widget": {"id": "new", "unit_key": "fcc"}}, {"fcc"}, _widgets())


def test_replace_request_accepts_replace_plan():
    assert conflicts_with_current_turn("Αντικατάστησε το FCC feed", {"action": "replace_widget", "target_id": "fcc-feed", "widget": {"id": "fcc-new", "unit_key": "fcc"}}, {"fcc"}, _widgets()) == []


def test_remove_request_rejects_update_plan():
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC", {"action": "update_widgets", "target_ids": ["fcc-feed"], "period": "8h"}, {"fcc"}, _widgets())


def test_add_request_rejects_remove_plan():
    assert conflicts_with_current_turn("Βάλε feed στο FCC", {"action": "remove_widget", "target_id": "fcc-feed"}, {"fcc"}, _widgets())


def test_restore_request_accepts_add_execution_plan():
    assert conflicts_with_current_turn("Επανέφερε το FCC feed", {"action": "add_widgets", "widgets": [{"id": "fcc-restored", "unit_key": "fcc"}]}, {"fcc"}, _widgets()) == []


def test_restore_request_rejects_remove_execution_plan():
    assert conflicts_with_current_turn("Επανέφερε το FCC feed", {"action": "remove_widget", "target_id": "fcc-feed"}, {"fcc"}, _widgets())


def test_unknown_target_id_is_rejected_for_explicit_unit_mutation():
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC", {"action": "remove_widget", "target_id": "missing-id"}, {"fcc"}, _widgets())


def test_multiple_explicit_units_accept_targets_within_requested_set():
    assert conflicts_with_current_turn("Αφαίρεσε τα feed από FCC και HCU", {"action": "remove_widgets", "target_ids": ["fcc-feed", "hcu-feed"]}, {"fcc", "hcu"}, _widgets()) == []


def test_multiple_explicit_units_reject_target_outside_requested_set():
    widgets = _widgets() + [{"id": "other-feed", "type": "trend", "unit_key": "other"}]
    assert conflicts_with_current_turn("Αφαίρεσε τα feed από FCC και HCU", {"action": "remove_widgets", "target_ids": ["fcc-feed", "other-feed"]}, {"fcc", "hcu"}, widgets)


def test_plain_question_has_no_explicit_action_family():
    assert explicit_action_families("Ποιο είναι το feed του FCC;") == set()


def test_empty_command_has_no_explicit_action_family():
    assert explicit_action_families("") == set()


def test_english_restore_phrase_maps_to_restore_only():
    assert explicit_action_families("Bring back the FCC feed") == {"restore"}


def test_english_restore_and_add_detects_both_actions():
    assert explicit_action_families("Bring back the FCC feed and add the HCU feed") == {"restore", "add"}


def test_greek_unaccented_restore_is_detected():
    assert explicit_action_families("Επαναφερε το FCC feed") == {"restore"}


def test_greek_accented_restore_is_detected():
    assert explicit_action_families("Επανέφερε το FCC feed") == {"restore"}


def test_case_insensitive_english_actions():
    assert explicit_action_families("REMOVE FCC feed AND ADD HCU feed") == {"remove", "add"}


def test_replace_synonym_swap_is_detected():
    assert explicit_action_families("Swap the FCC feed") == {"replace"}


def test_greek_delete_synonym_is_detected():
    assert explicit_action_families("Διέγραψε το FCC feed") == {"remove"}


def test_greek_add_synonym_is_detected():
    assert explicit_action_families("Πρόσθεσε feed στο FCC") == {"add"}
