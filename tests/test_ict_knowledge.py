from trading.ict_knowledge import foundation_sequence, load_ict_knowledge, strategy_rules

def test_foundation_sequence_matches_book_framework():
    assert foundation_sequence() == ("bias","location","draw","level","time","trigger")

def test_liquidity_is_preserved_as_narrative_target():
    data = load_ict_knowledge()
    assert data["framework"]["liquidity_first_interpretation"]["liquidity"] == "narrative and target"

def test_turtle_soup_targets_opposite_liquidity():
    rules = strategy_rules("turtle_soup")["rules"]
    assert "target opposite range liquidity" in rules
