"""Unit tests for opt-in AIML brain-file translation (enable_tx).

No network access: the translator is a mock that prepends "TX:" to text.
"""
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

import pytest

from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole
from ovos_solver_aiml_plugin import AIMLChatEngine, AimlBot, _translate_aiml_file


# ---------------------------------------------------------------------------
# Helper: a tiny fake AIML file for translation tests
# ---------------------------------------------------------------------------

_SAMPLE_AIML = """\
<?xml version="1.0" encoding="ISO-8859-1"?>
<aiml version="1.0">
<category>
<pattern>HELLO</pattern>
<template>Hi there!</template>
</category>
<category>
<pattern>WHAT IS YOUR NAME</pattern>
<template>My name is <bot name="name"/>.</template>
</category>
</aiml>
"""


def _make_fake_translator(prefix="TX:"):
    """Return a mock translator whose translate() prepends *prefix*."""
    tx = MagicMock()
    tx.translate.side_effect = lambda text, target, source="en": prefix + text
    return tx


# ---------------------------------------------------------------------------
# Tests for _translate_aiml_file
# ---------------------------------------------------------------------------

class TestTranslateAimlFile:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_src(self, content=_SAMPLE_AIML, name="test.aiml"):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def test_translates_pattern_and_template_text(self):
        src = self._write_src()
        dest = os.path.join(self.tmpdir, "out.aiml")
        tx = _make_fake_translator("TX:")
        result = _translate_aiml_file(src, dest, tx, "pt")
        assert result is True
        assert os.path.isfile(dest)
        content = open(dest).read()
        # Pattern text should be translated
        assert "TX:HELLO" in content
        # Template plain text should be translated
        assert "TX:Hi there!" in content

    def test_does_not_translate_bot_tag_attributes(self):
        src = self._write_src()
        dest = os.path.join(self.tmpdir, "out.aiml")
        tx = _make_fake_translator("TX:")
        _translate_aiml_file(src, dest, tx, "pt")
        content = open(dest).read()
        # The name attribute value ("name") inside <bot name="name"/> must be untouched
        assert 'name="name"' in content

    def test_returns_false_on_invalid_xml(self):
        src = self._write_src("<not valid xml <<<")
        dest = os.path.join(self.tmpdir, "out.aiml")
        tx = _make_fake_translator()
        result = _translate_aiml_file(src, dest, tx, "pt")
        assert result is False

    def test_translation_error_keeps_original_text(self):
        src = self._write_src()
        dest = os.path.join(self.tmpdir, "out.aiml")
        tx = MagicMock()
        tx.translate.side_effect = RuntimeError("network down")
        result = _translate_aiml_file(src, dest, tx, "pt")
        # Should still succeed (write file), just keep original text
        assert result is True
        content = open(dest).read()
        assert "Hi there!" in content or "HELLO" in content


# ---------------------------------------------------------------------------
# Tests for AIMLChatEngine translation integration
# ---------------------------------------------------------------------------

class TestAIMLChatEngineTranslation:
    """With enable_tx=True and a fake translator, requesting a non-English
    lang that has no local brain triggers brain-file translation into XDG."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Patch XDG path so we don't pollute the real user home
        self._orig_xdg = AimlBot.XDG_PATH
        AimlBot.XDG_PATH = self.tmpdir

    def teardown_method(self):
        AimlBot.XDG_PATH = self._orig_xdg
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _fake_load_tx_plugin(self, plug_id):
        """Returns a class whose instance is our fake translator."""
        tx = _make_fake_translator("TRANSLATED:")
        cls = MagicMock(return_value=tx)
        return cls

    def test_enable_tx_off_by_default(self):
        engine = AIMLChatEngine()
        assert engine.translate is False
        assert engine.translator is None

    def test_get_translator_returns_none_when_disabled(self):
        engine = AIMLChatEngine({"enable_tx": False})
        result = engine._get_translator()
        assert result is None

    def test_translated_brain_dir_created_for_new_lang(self):
        lang = "pt-pt"
        # Ensure no pre-existing brain for this lang in our fake XDG
        assert not os.path.isdir(os.path.join(self.tmpdir, lang))

        fake_cfg = MagicMock()
        fake_cfg.return_value.get.return_value = {}

        with patch("ovos_solver_aiml_plugin.load_tx_plugin", side_effect=self._fake_load_tx_plugin,
                   create=True) as mock_load:
            # Patch inside _get_translator via its imported names
            import ovos_solver_aiml_plugin as _m
            orig_get = _m.AIMLChatEngine._get_translator

            def _patched_get_translator(self_inner):
                tx = _make_fake_translator("TRANSLATED:")
                self_inner._translator_loaded = True
                self_inner.translator = tx
                return tx

            _m.AIMLChatEngine._get_translator = _patched_get_translator
            try:
                engine = AIMLChatEngine({"lang": lang, "enable_tx": True})
            finally:
                _m.AIMLChatEngine._get_translator = orig_get

        # The translated brain dir should have been written
        lang_dir = os.path.join(self.tmpdir, lang)
        assert os.path.isdir(lang_dir), f"Expected translated brain dir at {lang_dir}"
        aiml_files = [f for f in os.listdir(lang_dir) if f.endswith(".aiml")]
        assert aiml_files, "Expected .aiml files in translated brain dir"

    def test_fallback_to_english_when_translator_unavailable(self):
        """When enable_tx=True but translator cannot load, falls back to en-us."""
        lang = "de-de"
        import ovos_solver_aiml_plugin as _m
        orig_get = _m.AIMLChatEngine._get_translator

        def _no_translator(self_inner):
            self_inner._translator_loaded = True
            self_inner.translator = None
            return None

        _m.AIMLChatEngine._get_translator = _no_translator
        try:
            engine = AIMLChatEngine({"lang": lang, "enable_tx": True})
        finally:
            _m.AIMLChatEngine._get_translator = orig_get

        # Brain must still load (en-us fallback)
        assert engine.brain.brain_loaded is True
        assert engine.brain.lang == "en-us"

    def test_continue_chat_works_after_translation(self):
        """Engine remains functional (answers queries) after brain translation."""
        lang = "es-es"
        import ovos_solver_aiml_plugin as _m
        orig_get = _m.AIMLChatEngine._get_translator

        def _patched_get_translator(self_inner):
            tx = _make_fake_translator("TRANSLATED:")
            self_inner._translator_loaded = True
            self_inner.translator = tx
            return tx

        _m.AIMLChatEngine._get_translator = _patched_get_translator
        try:
            engine = AIMLChatEngine({"lang": lang, "enable_tx": True})
        finally:
            _m.AIMLChatEngine._get_translator = orig_get

        reply = engine.continue_chat([AgentMessage(role=MessageRole.USER, content="hello")])
        assert isinstance(reply, AgentMessage)
        assert reply.role == MessageRole.ASSISTANT
        # content may be empty if translated patterns don't match "hello" — that's fine;
        # the important thing is no exception was raised and the engine is operational.
