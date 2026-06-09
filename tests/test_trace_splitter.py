# HyperSpace-AGI v5.9 - Smoke tests: Trace Splitter
import pytest
from shared.domain.models import ReasoningTier
from shared.trace_splitter import split_trace, split_trace_segments


def test_shallow_trace():
    result = split_trace('task-1', 'qwen3.5:7b', 'short answer')
    assert result.tier == ReasoningTier.SHALLOW
    assert not result.was_truncated


def test_standard_trace():
    result = split_trace('task-2', 'qwen3.5:7b', ' '.join(['word'] * 700))
    assert result.tier == ReasoningTier.STANDARD


def test_bounded_trace():
    result = split_trace('task-3', 'deepseek-r1:14b', 'x' * 500, max_tokens=100)
    assert result.tier == ReasoningTier.BOUNDED
    assert result.was_truncated
    assert 'TRACE TRUNCATED' in result.raw_trace


def test_category_detection():
    result = split_trace('task-4', 'qwen3.5:7b', 'I will plan the steps first, then call the tool function')
    assert 'planning' in result.categories
    assert 'tool_call' in result.categories


def test_split_segments_deepseek():
    segments = split_trace_segments('preamble<think>step one<think>step two')
    assert len(segments) == 3


def test_split_segments_no_separator():
    trace = 'plain text without think tags'
    assert split_trace_segments(trace) == [trace]
