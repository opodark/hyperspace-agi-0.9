# HyperSpace-AGI v5.9 - Smoke tests: Request Classifier
import pytest
from shared.domain.models import ChatMessage, UserRequest, RequestFeatures, ServiceTier, WorkloadType
from control_plane.request_classifier import RequestClassifier


@pytest.fixture
def clf() -> RequestClassifier:
    return RequestClassifier()


def _req(text: str, **kw) -> UserRequest:
    return UserRequest(
        model_alias='auto',
        messages=[ChatMessage(role='user', content=text)],
        features=RequestFeatures(**kw),
    )


def test_coding_keyword(clf):
    assert clf.classify(_req('please refactor this python function')).workload_type == WorkloadType.CODING_ASSISTANT


def test_deep_reasoning_max_quality(clf):
    assert clf.classify(_req('what do you think?', user_priority=ServiceTier.MAX_QUALITY)).workload_type == WorkloadType.DEEP_REASONING


def test_deep_reasoning_keywords(clf):
    assert clf.classify(_req('analyze and explain why because therefore it makes sense')).workload_type == WorkloadType.DEEP_REASONING


def test_long_context_by_tokens(clf):
    assert clf.classify(_req('hello', estimated_context_tokens=20000)).workload_type == WorkloadType.LONG_CONTEXT_ANALYSIS


def test_tool_calling(clf):
    assert clf.classify(_req('get me the weather', requires_tools=True)).workload_type == WorkloadType.TOOL_CALLING


def test_fast_chat_default(clf):
    assert clf.classify(_req('hello how are you today')).workload_type == WorkloadType.FAST_CHAT
