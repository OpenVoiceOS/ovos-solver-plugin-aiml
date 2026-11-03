"""Regression tests: bot identity must reflect the ALICE/AIML lineage, not
Mycroft, and must be configurable.

This plugin is not Mycroft and OVOS does not carry Mycroft attribution, so
the AIML bot predicates (name, genus, age, ...) must never hardcode
"Mycroft" and must be overridable via config (bot_<predicate> keys).
"""
from ovos_solver_aiml_plugin import AIMLChatEngine, AimlBot


def _user(content):
    from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole
    return [AgentMessage(role=MessageRole.USER, content=content)]


def test_default_identity_is_not_mycroft():
    engine = AIMLChatEngine({"lang": "en-us"})
    for predicate in AimlBot.IDENTITY_DEFAULTS:
        assert engine.brain.kernel.getBotPredicate(predicate) != "Mycroft"
    assert engine.brain.kernel.getBotPredicate("name") == "A.L.I.C.E."
    assert engine.brain.kernel.getBotPredicate("genus") == "AIML"
    # "botmaster" is the role word the corpus interpolates a name into (e.g.
    # "My <botmaster> is <master>."), not a name itself - the person goes in
    # "master", not "botmaster".
    assert engine.brain.kernel.getBotPredicate("botmaster") == "master"
    assert engine.brain.kernel.getBotPredicate("master") == "Dr. Richard S. Wallace"


def test_configured_name_reaches_the_answer():
    engine = AIMLChatEngine({"lang": "en-us", "bot_name": "Zorb"})
    assert engine.brain.kernel.getBotPredicate("name") == "Zorb"
    reply = engine.continue_chat(_user("what is your name"), lang="en-us")
    assert "zorb" in reply.content.lower()


def test_botmaster_renders_grammatically_in_the_answer():
    # Regression: setting botmaster (a role word, "My <botmaster> is ...")
    # to a person's name instead of master produced "My Dr. Richard S.
    # Wallace is Dr. Richard S. Wallace." - ungrammatical. Assert against
    # the actual rendered reply, not just the predicate value, so a
    # correct-value-wrong-slot regression fails the suite.
    engine = AIMLChatEngine({"lang": "en-us"})
    reply = engine.continue_chat(_user("who is your botmaster"), lang="en-us")
    content = reply.content.lower()
    assert "wallace" in content
    assert "my dr. richard s. wallace is" not in content


def test_where_are_you_from_has_no_empty_holes():
    # Regression: birthplace/location were never set, so "WHERE ARE YOU
    # FROM" rendered "I am originally from . Now I live in . Where are
    # you?" with empty holes instead of bot-level values.
    engine = AIMLChatEngine({"lang": "en-us"})
    reply = engine.continue_chat(_user("where are you from"), lang="en-us")
    assert "from . " not in reply.content
    assert "live in . " not in reply.content
    assert "internet" in reply.content.lower()


def test_configured_identity_predicates_are_all_overridable():
    overrides = {f"bot_{k}": f"custom-{k}" for k in AimlBot.IDENTITY_DEFAULTS}
    overrides["lang"] = "en-us"
    engine = AIMLChatEngine(overrides)
    for predicate in AimlBot.IDENTITY_DEFAULTS:
        assert engine.brain.kernel.getBotPredicate(predicate) == f"custom-{predicate}"


def test_age_derives_from_alice_birth_year_not_mycroft():
    from datetime import date
    engine = AIMLChatEngine({"lang": "en-us"})
    expected = str(date.today().year - AimlBot.ALICE_BIRTH_YEAR)
    assert engine.brain.kernel.getBotPredicate("age") == expected


def test_invalid_birth_year_does_not_crash_construction():
    # A bad config value here must degrade with a warning, not raise -
    # QuestionSolversService.load_plugins has no try/except around plugin
    # construction, so an uncaught ValueError here would take down the whole
    # Persona, not just this handler.
    from datetime import date
    engine = AIMLChatEngine({"lang": "en-us", "bot_birth_year": "not-a-year"})
    expected = str(date.today().year - AimlBot.ALICE_BIRTH_YEAR)
    assert engine.brain.kernel.getBotPredicate("age") == expected


def test_non_string_predicate_value_does_not_crash_construction():
    # PatternMgr.setBotName calls .split() on the predicate value; a
    # non-string config value like {"bot_name": 123} must not reach it raw.
    engine = AIMLChatEngine({"lang": "en-us", "bot_name": 123})
    assert engine.brain.kernel.getBotPredicate("name") == "123"
