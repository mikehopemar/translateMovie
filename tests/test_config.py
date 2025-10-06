import os
from importlib import reload

import pytest

from translate_movie import core


def test_get_config_defaults(tmp_path, monkeypatch):
    # Ensure no env vars set
    for k in [
        "WHISPER_MODEL",
        "WHISPER_LANGUAGE",
        "OPENAI_ENDPOINT",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
    ]:
        monkeypatch.delenv(k, raising=False)

    cfg = core.get_config()
    assert cfg["WHISPER_MODEL"] == "large"
    assert cfg["WHISPER_LANGUAGE"] == "en"
    assert cfg["OPENAI_ENDPOINT"].startswith("http://")
    assert cfg["OPENAI_API_KEY"] == "lm-studio"
    assert cfg["OPENAI_MODEL"].startswith("qwen")


def test_get_config_from_env(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "medium")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    monkeypatch.setenv("OPENAI_ENDPOINT", "https://example.com/v1")

    cfg = core.get_config()
    assert cfg["WHISPER_MODEL"] == "medium"
    assert cfg["OPENAI_API_KEY"] == "secret-key"
    assert cfg["OPENAI_ENDPOINT"] == "https://example.com/v1"
