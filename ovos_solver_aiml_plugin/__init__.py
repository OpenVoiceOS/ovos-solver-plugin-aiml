import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from os import listdir, remove as remove_file, makedirs
from os.path import dirname, isfile, isdir, join
from typing import List, Optional

from ovos_plugin_manager.templates.agents import ChatEngine, AgentMessage, MessageRole
from ovos_utils.log import LOG
from ovos_utils.xdg_utils import xdg_data_home

# patch so aiml works with python > 3.7
time.clock = time.perf_counter
import aiml

# AIML tags whose text/tail must NOT be translated (structural or wildcard nodes)
_AIML_SKIP_TAGS = {
    "aiml", "category", "pattern", "that", "topic",
    "srai", "star", "thatstar", "topicstar",
    "bot", "get", "set", "input",
    "condition", "li", "random",
    "think", "learn",
    "system", "javascript",
}

# Tags whose direct text content is human-readable and should be translated
_AIML_TRANSLATE_TAGS = {"pattern", "template"}


def _translate_aiml_file(src_path: str, dest_path: str, translator, target_lang: str) -> bool:
    """Translate human-readable text in an AIML file, writing the result to dest_path.

    Only text directly inside ``<pattern>`` and ``<template>`` nodes is translated.
    AIML structural tags, ``<srai>``, ``<star>``, ``*`` wildcards, ``<bot>`` tags, and
    all XML attributes are left untouched.  Returns True on success, False on any error.
    """
    try:
        tree = ET.parse(src_path)
        root = tree.getroot()
    except Exception as e:
        LOG.warning(f"Failed to parse AIML file {src_path}: {e}")
        return False

    def _tx(text: str) -> str:
        if not text or not text.strip():
            return text
        # Preserve leading/trailing whitespace around the translated content
        leading = text[: len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()):]
        stripped = text.strip()
        if not stripped:
            return text
        try:
            translated = translator.translate(stripped, target=target_lang, source="en")
            return leading + (translated or stripped) + trailing
        except Exception as e:
            LOG.warning(f"Translation of AIML text failed ({e}); keeping original")
            return text

    def _translate_template_node(node):
        """Recursively translate text/tail in a <template> subtree, skipping structural tags."""
        tag = node.tag if isinstance(node.tag, str) else ""
        # Strip namespace if present
        local = tag.split("}")[-1] if "}" in tag else tag

        if local in _AIML_SKIP_TAGS and local != "template":
            # Translate the tail (text after this tag's closing, before next sibling)
            if node.tail and node.tail.strip():
                node.tail = _tx(node.tail)
            return  # do not descend into structural/skip tags

        # Translate direct text of this node if it is human-readable
        if local not in _AIML_SKIP_TAGS:
            if node.text and node.text.strip():
                node.text = _tx(node.text)
            if node.tail and node.tail.strip():
                node.tail = _tx(node.tail)

        for child in node:
            _translate_template_node(child)

    for category in root.iter("category"):
        for child in category:
            tag = child.tag if isinstance(child.tag, str) else ""
            local = tag.split("}")[-1] if "}" in tag else tag
            if local == "pattern":
                # Translate pattern text but preserve wildcards (* and _)
                if child.text:
                    # Replace wildcard tokens temporarily, translate, restore
                    raw = child.text
                    # Only translate if it contains non-wildcard text
                    words = raw.strip().split()
                    non_wc = [w for w in words if w not in ("*", "_")]
                    if non_wc:
                        child.text = _tx(raw)
            elif local == "template":
                # Translate direct text of template node
                if child.text and child.text.strip():
                    child.text = _tx(child.text)
                if child.tail and child.tail.strip():
                    child.tail = _tx(child.tail)
                for sub in child:
                    _translate_template_node(sub)

    try:
        tree.write(dest_path, encoding="unicode", xml_declaration=True)
        return True
    except Exception as e:
        LOG.warning(f"Failed to write translated AIML to {dest_path}: {e}")
        return False


class AimlBot:
    XDG_PATH = f"{xdg_data_home()}/aiml"
    makedirs(XDG_PATH, exist_ok=True)

    def __init__(self, lang="en-us", settings=None):
        self.settings = settings or {}
        self.lang = lang
        self.kernel = aiml.Kernel()
        xdg_lang = f"{self.XDG_PATH}/{lang}"
        if isdir(xdg_lang) and any(f.endswith(".aiml") for f in os.listdir(xdg_lang)):
            # user-defined or previously translated aiml
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
    def __init__(self, config=None):
        config = config or {"lang": "en-us"}
        super().__init__(config)

        # Translation is opt-in and OFF by default.
        self.translate: bool = self.config.get("enable_tx", False)
        self.translator = None
        self._translator_loaded: bool = False

        lang = self.config.get("lang") or "en-us"
        self.brain = self._resolve_brain(lang)
        self.brain.load_brain()

    # ------------------------------------------------------------------
    # translator helpers
    # ------------------------------------------------------------------

    def _get_translator(self):
        """Lazily load a translation plugin.

        Returns the translator instance, or ``None`` if translation is
        disabled or the plugin cannot be loaded.  Never raises.
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
                LOG.warning(
                    f"Translation plugin not available '{plug_id}': "
                    "brain-file translation disabled"
                )
            else:
                self.translator = clazz(config=lang_cfg.get(plug_id, {}))
                LOG.debug(f"Loaded translation plugin: '{plug_id}'")
        except Exception as e:
            LOG.warning(
                f"Failed to load translation plugin ({e}): "
                "brain-file translation disabled"
            )
            self.translator = None
        return self.translator

    # ------------------------------------------------------------------
    # brain resolution (with optional translation)
    # ------------------------------------------------------------------

    def _resolve_brain(self, lang: str) -> AimlBot:
        """Return an AimlBot for *lang*, translating the en-us brain if needed.

        Translation is attempted when ALL of the following hold:
        - ``enable_tx`` is True
        - *lang* is not English
        - No bundled or XDG brain exists for *lang*
        - A translator plugin loads successfully

        On any failure the method falls back silently to the en-us brain.
        """
        if lang == "en-us":
            return AimlBot(lang, self.config)

        bot = AimlBot(lang, self.config)
        if bot.has_brain:
            return bot

        # No local brain for this lang — try translation if enabled
        if self.translate:
            tx_bot = self._try_translate_brain(lang)
            if tx_bot is not None:
                return tx_bot

        LOG.info(f"No AIML brain for '{lang}', falling back to en-us")
        return AimlBot("en-us", self.config)

    def _try_translate_brain(self, lang: str) -> Optional[AimlBot]:
        """Translate the en-us brain into *lang*, write to XDG, return AimlBot.

        Returns None on any failure so the caller can fall back gracefully.
        """
        translator = self._get_translator()
        if translator is None:
            return None

        src_dir = join(dirname(__file__), "aiml_data", "en-us")
        if not isdir(src_dir):
            LOG.warning("Bundled en-us AIML brain not found; cannot translate")
            return None

        dest_dir = join(AimlBot.XDG_PATH, lang)
        makedirs(dest_dir, exist_ok=True)

        aiml_files = [f for f in os.listdir(src_dir) if f.endswith(".aiml")]
        if not aiml_files:
            return None

        LOG.info(f"Translating {len(aiml_files)} AIML brain files to '{lang}' (this runs once)")
        success_count = 0
        for filename in aiml_files:
            src = join(src_dir, filename)
            dest = join(dest_dir, filename)
            if _translate_aiml_file(src, dest, translator, lang):
                success_count += 1
            else:
                LOG.warning(f"Translation of {filename} failed; skipping")

        if success_count == 0:
            LOG.warning(f"All AIML file translations failed for '{lang}'; falling back to en-us")
            return None

        LOG.info(f"Translated {success_count}/{len(aiml_files)} AIML files to '{lang}'")
        bot = AimlBot(lang, self.config)
        if bot.has_brain:
            return bot
        return None

    # ------------------------------------------------------------------
    # ChatEngine interface
    # ------------------------------------------------------------------

    def continue_chat(self, messages: List[AgentMessage],
                      session_id: str = "default",
                      lang: Optional[str] = None,
                      units: Optional[str] = None) -> AgentMessage:
        """Answer the latest user message via the AIML brain.

        Args:
            messages: Conversation history; the last user turn is answered.
            session_id: Session identifier (AIML keeps no per-session state here).
            lang: Optional BCP-47 language code.
            units: Optional unit system (unused).

        Returns:
            AgentMessage: The assistant reply.
        """
        query = next((m.content for m in reversed(messages)
                      if m.role == MessageRole.USER), "")
        answer = self.brain.ask(query) if query else ""
        return AgentMessage(role=MessageRole.ASSISTANT, content=answer or "")


if __name__ == "__main__":
    print(AimlBot.XDG_PATH)
    bot = AIMLChatEngine()
    print(bot.continue_chat([AgentMessage(role=MessageRole.USER, content="hello!")]).content)
