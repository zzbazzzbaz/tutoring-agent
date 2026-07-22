from tutoring.chat.server_client import state_is_interrupted


def test_state_is_interrupted_true_when_next_nonempty():
    assert state_is_interrupted({"next": ["__interrupt__"], "values": {}, "tasks": []}) is True


def test_state_is_interrupted_false_when_next_empty():
    assert state_is_interrupted({"next": [], "values": {}, "tasks": []}) is False


def test_state_is_interrupted_false_when_missing_next():
    assert state_is_interrupted({"values": {}}) is False
