"""Unit tests for opt-in query/response translation (enable_tx).

The bundled AIML brain is English. When ``enable_tx`` is set, a non-English
user query is translated into English, answered by the brain, and the answer
translated back. No network access: the translator is a mock.
"""
from unittest.mock import MagicMock

from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole
from ovos_solver_aiml_plugin import AIMLChatEngine


def _user(content):
    return [AgentMessage(role=MessageRole.USER, content=content)]


def _fake_translator():
    """A translator that tags text with its direction so we can assert it."""
    tx = MagicMock()
    tx.translate.side_effect = lambda text, target, source: f"[{source}->{target}]{text}"
    return tx


def test_translation_disabled_by_default():
    engine = AIMLChatEngine({"lang": "en-us"})
    assert engine.translate is False
    # English query answered directly, no translator ever loaded
    reply = engine.continue_chat(_user("hello"), lang="en-us")
    assert reply.content.strip()
    assert engine.translator is None


def test_english_query_never_translated_even_when_enabled():
    engine = AIMLChatEngine({"lang": "en-us", "enable_tx": True},
                            translator=_fake_translator())
    engine.continue_chat(_user("hello"), lang="en-US")
    engine.translator.translate.assert_not_called()


def test_non_english_query_translated_both_ways():
    tx = _fake_translator()
    engine = AIMLChatEngine({"lang": "en-us", "enable_tx": True}, translator=tx)
    # stub the brain so it always answers (the fake-translated query won't match)
    engine.brain.ask = lambda utterance: f"answer to: {utterance}"
    reply = engine.continue_chat(_user("ola"), lang="pt-pt")

    # query translated pt -> en before hitting the brain
    inbound = tx.translate.call_args_list[0]
    assert inbound.kwargs["source"] == "pt" and inbound.kwargs["target"] == "en"
    # answer translated en -> pt on the way out
    outbound = tx.translate.call_args_list[-1]
    assert outbound.kwargs["source"] == "en" and outbound.kwargs["target"] == "pt"
    assert reply.content.startswith("[en->pt]")


def test_continue_chat_accepts_tools_kwarg_none():
    """ChatEngine base contract: ``tools`` must be accepted (and ignored)
    even though AIMLChatEngine is not tool-capable (pure pattern matching)."""
    engine = AIMLChatEngine({"lang": "en-us"})
    reply = engine.continue_chat(_user("hello"), lang="en-us", tools=None)
    assert isinstance(reply, AgentMessage)
    assert reply.role == MessageRole.ASSISTANT


def test_continue_chat_accepts_tools_kwarg_list():
    """Passing a non-empty ``tools`` list must not raise, since the base
    ChatEngine.continue_chat wrapper may call subclasses with tools=."""
    engine = AIMLChatEngine({"lang": "en-us"})
    reply = engine.continue_chat(
        _user("hello"), lang="en-us",
        tools=[{"type": "function", "function": {"name": "noop"}}],
    )
    assert isinstance(reply, AgentMessage)
    assert reply.role == MessageRole.ASSISTANT


def test_missing_translator_degrades_gracefully():
    # enable_tx on, but no plugin available -> never raises, answers as-is
    engine = AIMLChatEngine({"lang": "en-us", "enable_tx": True})
    engine._ensure_translator = lambda: None
    reply = engine.continue_chat(_user("hola"), lang="es")
    assert isinstance(reply.content, str)


def test_brain_files_are_not_translated():
    """Regression: translation is query-level only and must NOT touch brain files."""
    import ovos_solver_aiml_plugin as mod
    assert not hasattr(mod, "_translate_aiml_file")
    assert not hasattr(AIMLChatEngine, "_try_translate_brain")
