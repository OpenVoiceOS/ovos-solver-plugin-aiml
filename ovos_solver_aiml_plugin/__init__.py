import os
import time
from datetime import date
from os import listdir, remove as remove_file, makedirs
from os.path import dirname, isfile, isdir, join
from typing import List, Optional

from ovos_plugin_manager.templates.agents import ChatEngine, AgentMessage, MessageRole

try:
    from ovos_plugin_manager.templates.agents import ToolsArg
except ImportError:  # pragma: no cover - older ovos-plugin-manager
    ToolsArg = None
from ovos_utils.log import LOG
from ovos_utils.xdg_utils import xdg_data_home

# patch so aiml works with python > 3.7
time.clock = time.perf_counter
import aiml


class AimlBot:
    XDG_PATH = f"{xdg_data_home()}/aiml"
    makedirs(XDG_PATH, exist_ok=True)

    def __init__(self, lang="en-us", settings=None):
        self.settings = settings or {}
        self.lang = lang
        self.kernel = aiml.Kernel()
        xdg_lang = f"{self.XDG_PATH}/{lang}"
        if isdir(xdg_lang) and any(f.endswith(".aiml") for f in os.listdir(xdg_lang)):
            # user-defined aiml
            self.aiml_path = xdg_lang
        else:
            # bundled curated aiml (may not exist for non-English langs)
            bundled = f"{dirname(__file__)}/aiml_data/{lang}"
            self.aiml_path = bundled if isdir(bundled) else None
        self.brain_path = f"{self.XDG_PATH}/{lang}/bot_brain.brn"
        makedirs(f"{self.XDG_PATH}/{lang}", exist_ok=True)
        self.line_count = 1
        self.save_loop_threshold = int(self.settings.get('save_loop_threshold', 4))
        self.brain_loaded = False

    @property
    def has_brain(self) -> bool:
        """True when a valid brain source (bundled or XDG) exists for this lang."""
        return self.aiml_path is not None

    def load_brain(self):
        if not self.has_brain:
            LOG.warning(f"No AIML brain available for lang '{self.lang}'")
            return
        LOG.info('Loading Brain')
        if isfile(self.brain_path):
            self.kernel.bootstrap(brainFile=self.brain_path)
        else:
            aimls = listdir(self.aiml_path)
            for aiml_file in aimls:
                if aiml_file.endswith(".aiml"):
                    self.kernel.learn(join(self.aiml_path, aiml_file))
            self.kernel.saveBrain(self.brain_path)

        self.kernel.setBotPredicate("name", "Mycroft")
        self.kernel.setBotPredicate("species", "AI")
        self.kernel.setBotPredicate("genus", "Mycroft")
        self.kernel.setBotPredicate("family", "virtual personal assistant")
        self.kernel.setBotPredicate("order", "artificial intelligence")
        self.kernel.setBotPredicate("class", "computer program")
        self.kernel.setBotPredicate("kingdom", "machine")
        self.kernel.setBotPredicate("hometown", "127.0.0.1")
        self.kernel.setBotPredicate("botmaster", "master")
        self.kernel.setBotPredicate("master", "the community")
        # https://api.github.com/repos/MycroftAI/mycroft-core created_at date
        self.kernel.setBotPredicate("age", str(date.today().year - 2016))

        self.brain_loaded = True
        return

    def reset_brain(self):
        LOG.debug('Deleting brain file')
        # delete the brain file and reset memory
        remove_file(self.brain_path)
        self.soft_reset_brain()
        return

    def ask_brain(self, utterance):
        response = self.kernel.respond(utterance)
        # make a security copy once in a while
        if (self.line_count % self.save_loop_threshold) == 0:
            self.kernel.saveBrain(self.brain_path)
        self.line_count += 1
        return response

    def soft_reset_brain(self):
        # Only reset the active kernel memory
        self.kernel.resetBrain()
        self.brain_loaded = False
        return

    def ask(self, utterance):
        if not self.brain_loaded:
            self.load_brain()
        if not self.brain_loaded:
            return None
        answer = self.ask_brain(utterance)
        if answer != "":
            return answer

    def shutdown(self):
        if self.brain_loaded:
            self.kernel.saveBrain(self.brain_path)
            self.kernel.resetBrain()  # Manual remove


class AIMLChatEngine(ChatEngine):
    """AIML chatbot agent.

    The bundled brain is English. Non-English queries are handled by translating
    the user utterance into English, querying the brain, then translating the
    answer back. Translation is **opt-in** (``enable_tx``, default ``False``) so
    a plain install never depends on a translate plugin and English deployments
    pay no cost.

    Translation agents tend to be instantiated repeatedly, so a **remote**
    translation service is strongly recommended when enabling this — set
    ``translate_plugin`` (or the global ``language.translation_module``) to a
    server-backed plugin such as ``ovos-translate-plugin-server``.
    """

    # language of the bundled brain
    BRAIN_LANG = "en"

    def __init__(self, config=None, translator=None):
        config = config or {"lang": "en-us"}
        super().__init__(config)

        # translation is opt-in and OFF by default
        self.translate: bool = self.config.get("enable_tx", False)
        self.translator = translator
        self._translator_loaded: bool = translator is not None

        self.brain = AimlBot("en-us", self.config)
        self.brain.load_brain()

    # ------------------------------------------------------------------
    # translation helpers (query in / answer out, like a search engine)
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_lang(lang: Optional[str]) -> str:
        """Reduce a BCP-47 tag to its primary language subtag, lowercased."""
        if not lang:
            return "en"
        return lang.split("-")[0].lower()

    def _ensure_translator(self):
        """Lazily load a translation plugin on first non-English turn.

        Returns the translator, or ``None`` if translation is disabled or no
        plugin could be loaded. Never raises: a missing plugin degrades to
        answering in the original language (usually English).
        """
        if not self.translate:
            return None
        if self._translator_loaded:
            return self.translator
        self._translator_loaded = True
        try:
            from ovos_config import Configuration
            from ovos_plugin_manager.language import load_tx_plugin
            lang_cfg = Configuration().get("language", {})
            plug_id = (self.config.get("translate_plugin") or
                       lang_cfg.get("translation_module", "ovos-translate-plugin-server"))
            clazz = load_tx_plugin(plug_id)
            if clazz is None:
                LOG.warning(f"Translation plugin not available '{plug_id}': "
                            "non-English queries handled as-is")
            else:
                self.translator = clazz(config=lang_cfg.get(plug_id, {}))
                LOG.debug(f"Loaded translation plugin: '{plug_id}'")
        except Exception as e:
            LOG.warning(f"Failed to load translation plugin ({e}): "
                        "non-English queries handled as-is")
            self.translator = None
        return self.translator

    def _to_brain_lang(self, text: str, lang: str) -> str:
        """Translate user ``text`` from ``lang`` into the brain language."""
        if lang == self.BRAIN_LANG or not text:
            return text
        translator = self._ensure_translator()
        if translator is None:
            return text
        try:
            return translator.translate(text, target=self.BRAIN_LANG, source=lang)
        except Exception as e:
            LOG.warning(f"Translation to '{self.BRAIN_LANG}' failed ({e}); using original text")
            return text

    def _from_brain_lang(self, text: str, lang: str) -> str:
        """Translate the brain ``text`` back from the brain language into ``lang``."""
        if lang == self.BRAIN_LANG or not text:
            return text
        translator = self._ensure_translator()
        if translator is None:
            return text
        try:
            return translator.translate(text, target=lang, source=self.BRAIN_LANG)
        except Exception as e:
            LOG.warning(f"Translation from '{self.BRAIN_LANG}' failed ({e}); using original text")
            return text

    # ------------------------------------------------------------------
    # ChatEngine interface
    # ------------------------------------------------------------------
    def continue_chat(self, messages: List[AgentMessage],
                      session_id: str = "default",
                      lang: Optional[str] = None,
                      units: Optional[str] = None,
                      tools: "ToolsArg" = None) -> AgentMessage:
        """Answer the latest user message via the AIML brain.

        The user query is translated into the brain language, answered, and the
        answer translated back (both no-ops unless ``enable_tx`` is set and the
        language differs from the brain language).

        ``tools`` is accepted for ``ChatEngine`` contract conformance and
        ignored: AIML is pure pattern matching and cannot invoke tools. The
        agentic-loop ReAct fallback depends on non-tool engines being callable
        with ``tools=``.
        """
        query = next((m.content for m in reversed(messages)
                      if m.role == MessageRole.USER), "")
        if not query:
            return AgentMessage(role=MessageRole.ASSISTANT, content="")

        lang = self._norm_lang(lang or self.config.get("lang"))
        en_query = self._to_brain_lang(query, lang)
        answer = self.brain.ask(en_query) or ""
        answer = self._from_brain_lang(answer, lang)
        return AgentMessage(role=MessageRole.ASSISTANT, content=answer)


if __name__ == "__main__":
    print(AimlBot.XDG_PATH)
    bot = AIMLChatEngine()
    print(bot.continue_chat([AgentMessage(role=MessageRole.USER, content="hello!")]).content)
