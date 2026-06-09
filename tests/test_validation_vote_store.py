# HyperSpace-AGI v5.9 - Smoke tests: Validation Vote Store
import pytest
from shared.domain.models import ValidationVote, ContestStatus
from worker.validation_vote_store import ValidationVoteStore


@pytest.fixture
def store(tmp_path):
    return ValidationVoteStore(state_dir=str(tmp_path))


def _vote(memory_id: str, vote: str, confidence: float = 0.8) -> ValidationVote:
    return ValidationVote(
        memory_id=memory_id, dream_id='dream-001',
        voter_model_id='qwen3.5:7b', vote=vote, confidence=confidence,
    )


def test_cast_and_retrieve(store):
    v = _vote('mem-001', 'confirm')
    store.cast(v)
    votes = store.votes_for_memory('mem-001')
    assert len(votes) == 1
    assert votes[0].vote == 'confirm'


def test_tally_confirm_majority(store):
    for _ in range(3):
        store.cast(_vote('mem-002', 'confirm'))
    store.cast(_vote('mem-002', 'retract'))
    tally = store.tally('mem-002')
    assert tally.confirm_count == 3
    assert tally.quorum_reached
    assert tally.resolution == ContestStatus.RESOLVED_CONFIRM


def test_tally_retract_majority(store):
    for _ in range(3):
        store.cast(_vote('mem-003', 'retract'))
    tally = store.tally('mem-003')
    assert tally.resolution == ContestStatus.RESOLVED_RETRACT


def test_no_quorum(store):
    store.cast(_vote('mem-004', 'confirm'))
    store.cast(_vote('mem-004', 'confirm'))
    tally = store.tally('mem-004')
    assert not tally.quorum_reached
    assert tally.resolution == ContestStatus.OPEN
