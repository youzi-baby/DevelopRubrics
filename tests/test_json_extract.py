"""Tests for JSON substring extraction from LLM outputs."""

from __future__ import annotations

from adarubric.llm.json_extract import extract_json_substring, strip_thinking


def test_fenced_json_block():
    raw = 'Here you go:\n```json\n{"a": 1}\n```\nThanks'
    assert extract_json_substring(raw) == '{"a": 1}'


def test_plain_object():
    assert extract_json_substring('prefix {"x": true} suffix') == '{"x": true}'


def test_nested_braces():
    raw = '{"outer": {"inner": 2}}'
    assert extract_json_substring(raw) == raw


def test_strip_thinking_block():
    raw = '<think>{"scratch": true}</think>\n{"final": true}'
    assert strip_thinking(raw) == '{"final": true}'
    assert extract_json_substring(raw) == '{"final": true}'


def test_strip_thinking_block_case_insensitive():
    raw = '<THINK>private reasoning</THINK>\n[{"rank": 1}]'
    assert extract_json_substring(raw) == '[{"rank": 1}]'
