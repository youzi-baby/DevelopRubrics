"""Tests for OpenAI-compatible client configuration helpers."""

from __future__ import annotations

import pytest

from adarubric.llm.openai_client import _extra_body_from_env, parse_extra_body


def test_extra_body_from_env_json_object():
    assert _extra_body_from_env('{"chat_template_kwargs": {"enable_thinking": true}}') == {
        "chat_template_kwargs": {"enable_thinking": True}
    }


def test_parse_extra_body_accepts_config_object():
    value = {"chat_template_kwargs": {"enable_thinking": True}}
    assert parse_extra_body(value) == value


def test_extra_body_from_env_rejects_non_object():
    with pytest.raises(ValueError, match="must be a JSON object"):
        _extra_body_from_env("[1, 2, 3]")
