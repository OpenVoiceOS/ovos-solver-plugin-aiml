"""Full-pipeline end-to-end test for ovos-solver-plugin-aiml via the persona pipeline.

Proves:
  1. An utterance flows through the real OVOS intent pipeline, hits the persona
     pipeline plugin backed by AIMLSolver, and produces a ``speak`` message.
  2. Per-session memory is recorded: the live PersonaService accumulates USER +
     ASSISTANT turns keyed by session_id, and an unknown session has no history.

No network access, no downloads.  AIMLSolver uses bundled AIML brain files —
``hello`` reliably returns ``Hi there!`` from the en-us corpus.
"""
import json
import os
import tempfile

import pytest

ovoscope = pytest.importorskip("ovoscope")
pytest.importorskip("ovos_persona")

from ovos_bus_client.message import Message
from ovos_bus_client.session import Session, SessionManager

from ovoscope import (
    PERSONA_PIPELINE,
    CaptureSession,
    get_minicroft,
    is_pipeline_available,
)

if not is_pipeline_available(PERSONA_PIPELINE):
    pytest.skip("ovos-persona-pipeline-plugin not installed", allow_module_level=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERSONA_NAME = "AimlBot"
# "hello" is answered by the bundled AIML salutations/default corpus
TEST_UTTERANCE = "hello"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_personas_dir(name: str = PERSONA_NAME) -> str:
    """Write a minimal AIML persona JSON into a temp directory and return the path."""
    tmpdir = tempfile.mkdtemp()
    persona = {
        "name": name,
        "handlers": ["ovos-solver-aiml-plugin"],
        "ovos-solver-aiml-plugin": {
            "lang": "en-us",
        },
    }
    with open(os.path.join(tmpdir, f"{name}.json"), "w") as fh:
        json.dump(persona, fh)
    return tmpdir


def _utterance_msg(utterance: str, sess: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utterance], "lang": sess.lang},
        {"session": sess.serialize()},
    )


# ---------------------------------------------------------------------------
# Module-level MiniCroft (shared across tests for speed)
# ---------------------------------------------------------------------------

PERSONAS_PATH = _make_personas_dir(PERSONA_NAME)

PIPELINE_CONFIG = {
    "persona": {
        "personas_path": PERSONAS_PATH,
        "default_persona": PERSONA_NAME,
        "short-term-memory": True,
        "handle_fallback": True,
        "ignore_plugin_personas": True,
    }
}

TEST_PIPELINE = [
    "ovos-persona-pipeline-plugin-high",
    "ovos-persona-pipeline-plugin-low",
]


@pytest.fixture(scope="module")
def mc():
    croft = get_minicroft(
        skill_ids=[],
        default_pipeline=TEST_PIPELINE,
        pipeline_config=PIPELINE_CONFIG,
    )
    yield croft
    croft.stop()


# ---------------------------------------------------------------------------
# Helpers that need the live croft
# ---------------------------------------------------------------------------

def _get_persona_service(croft):
    return croft.intents.pipeline_plugins["ovos-persona-pipeline-plugin"]


def _drive_utterance(croft, sess: Session, utterance: str, timeout: int = 60):
    cap = CaptureSession(
        croft,
        eof_msgs=["ovos.utterance.handled", "ovos.utterance.cancelled"],
    )
    cap.capture(_utterance_msg(utterance, sess), timeout=timeout)
    return cap.finish()


# ---------------------------------------------------------------------------
# Test 1: AIML persona speaks through the full pipeline
# ---------------------------------------------------------------------------

class TestAimlPersonaSpeaksThroughPipeline:
    """The utterance must traverse the full OVOS intent pipeline, be handled by
    AIMLSolver (pattern-matching, no network), and produce a non-empty speak message."""

    def test_pipeline_produces_speak(self, mc):
        sess = Session(session_id="aiml-e2e-speak-test")
        SessionManager.sessions[sess.session_id] = sess

        messages = _drive_utterance(mc, sess, TEST_UTTERANCE, timeout=60)

        msg_types = [m.msg_type for m in messages]
        speak_msgs = [m for m in messages if m.msg_type == "speak"]

        assert speak_msgs, (
            f"Expected at least one 'speak' message; got msg_types: {msg_types}"
        )
        spoken = speak_msgs[0].data.get("utterance", "")
        assert spoken.strip(), (
            f"'speak' message had an empty utterance; data={speak_msgs[0].data}"
        )

    def test_aiml_answers_locally_without_network(self, mc):
        """Verify AIMLSolver returns a non-empty answer for 'hello' using the bundled brain."""
        from ovos_solver_aiml_plugin import AIMLSolver
        solver = AIMLSolver({"lang": "en-us"})
        answer = solver.get_spoken_answer(TEST_UTTERANCE)
        assert answer and answer.strip(), (
            f"AIMLSolver returned empty answer for '{TEST_UTTERANCE}'"
        )

    def test_speak_non_empty_for_secondary_utterance(self, mc):
        sess = Session(session_id="aiml-e2e-speak-what")
        SessionManager.sessions[sess.session_id] = sess

        messages = _drive_utterance(mc, sess, "what is your name", timeout=60)

        for msg in messages:
            if msg.msg_type == "speak":
                assert msg.data.get("utterance", "").strip(), (
                    f"speak message has empty utterance: {msg.data}"
                )
                return
        pytest.fail(
            f"No 'speak' message found. "
            f"Message types: {[m.msg_type for m in messages]}"
        )


# ---------------------------------------------------------------------------
# Test 2: per-session memory is recorded
# ---------------------------------------------------------------------------

class TestPerSessionMemory:
    """PersonaService records USER+ASSISTANT turns per session_id after a real
    pipeline turn driven through MiniCroft."""

    def test_user_turn_recorded_in_memory(self, mc):
        svc = _get_persona_service(mc)
        sess = Session(session_id="aiml-e2e-mem-user")
        SessionManager.sessions[sess.session_id] = sess

        persona = svc.personas.get(PERSONA_NAME)
        assert persona is not None, f"Persona '{PERSONA_NAME}' not loaded"
        assert persona.memory is not None, "Persona must have short-term memory enabled"

        _drive_utterance(mc, sess, TEST_UTTERANCE, timeout=60)

        history = persona.memory.get_history(sess.session_id)
        contents = [m.content for m in history]
        assert any(TEST_UTTERANCE in c for c in contents), (
            f"User utterance not found in memory for session {sess.session_id}. "
            f"History: {contents}"
        )

    def test_assistant_response_recorded_in_memory(self, mc):
        svc = _get_persona_service(mc)
        sess = Session(session_id="aiml-e2e-mem-assistant")
        SessionManager.sessions[sess.session_id] = sess

        persona = svc.personas.get(PERSONA_NAME)
        assert persona is not None
        assert persona.memory is not None

        _drive_utterance(mc, sess, TEST_UTTERANCE, timeout=60)

        from ovos_plugin_manager.templates.agents import MessageRole
        history = persona.memory.get_history(sess.session_id)
        roles = [m.role for m in history]
        assert MessageRole.ASSISTANT in roles, (
            f"No ASSISTANT turn recorded in memory. History roles: {roles}"
        )

    def test_unknown_session_has_empty_history(self, mc):
        svc = _get_persona_service(mc)
        persona = svc.personas.get(PERSONA_NAME)
        assert persona is not None
        assert persona.memory is not None

        sess = Session(session_id="aiml-e2e-mem-known2")
        SessionManager.sessions[sess.session_id] = sess
        _drive_utterance(mc, sess, TEST_UTTERANCE, timeout=60)

        unknown_history = persona.memory.get_history("session-that-never-existed")
        assert unknown_history == [], (
            f"Expected empty history for unknown session, got: {unknown_history}"
        )

    def test_same_session_accumulates_turns(self, mc):
        svc = _get_persona_service(mc)
        sess = Session(session_id="aiml-e2e-mem-accumulate")
        SessionManager.sessions[sess.session_id] = sess

        persona = svc.personas.get(PERSONA_NAME)
        assert persona is not None
        assert persona.memory is not None
        persona.memory.session2history.pop(sess.session_id, None)

        _drive_utterance(mc, sess, "hello", timeout=60)
        _drive_utterance(mc, sess, "what is your name", timeout=60)

        history = persona.memory.get_history(sess.session_id)
        assert len(history) >= 2, (
            f"Expected at least 2 history entries after two turns, got {len(history)}: "
            f"{[m.content for m in history]}"
        )
