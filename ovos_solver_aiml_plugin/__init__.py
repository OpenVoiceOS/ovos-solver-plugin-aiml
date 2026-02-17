import os
import time
from datetime import date
from os import listdir, remove as remove_file, makedirs
from os.path import dirname, isfile, isdir
from typing import Dict, Optional, List, Any, Tuple

from ovos_plugin_manager.templates.agents import RetrievalEngine
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
        if isdir(xdg_lang):
            # user defined aiml
            self.aiml_path = xdg_lang
        else:
            # bundled curated aiml
            self.aiml_path = f"{dirname(__file__)}/aiml_data/{lang}"
        self.brain_path = f"{self.XDG_PATH}/{lang}/bot_brain.brn"
        makedirs(f"{self.XDG_PATH}/{lang}", exist_ok=True)
        self.line_count = 1
        self.save_loop_threshold = int(self.settings.get('save_loop_threshold', 4))
        self.brain_loaded = False

    def load_brain(self):
        LOG.info('Loading Brain')
        if isfile(self.brain_path):
            self.kernel.bootstrap(brainFile=self.brain_path)
        else:
            aimls = listdir(self.aiml_path)
            for aiml in aimls:
                self.kernel.learn(os.path.join(self.aiml_path, aiml))
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
        answer = self.ask_brain(utterance)
        if answer != "":
            return answer

    def shutdown(self):
        if self.brain_loaded:
            self.kernel.saveBrain(self.brain_path)
            self.kernel.resetBrain()  # Manual remove


class AIMLSolver(RetrievalEngine):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {"lang": "en-us"}
        lang = config.get("lang") or "en-us"
        if lang != "en-us" and lang not in os.listdir(AimlBot.XDG_PATH):
            config["lang"] = "en-us"
        super().__init__(config)
        self.brain = AimlBot(self.config.get("lang"))
        self.brain.load_brain()

    def query(self, query: str, lang: Optional[str] = None, k: int = 3) -> List[Tuple[str, float]]:
        """
        Searches the knowledge base for relevant documents or data.

        Args:
            query: The search string.
            lang: BCP-47 language code.
            k: The maximum number of results to return.

        Returns:
            List of tuples (content, score) for the top k matches.
        """
        return [(self.brain.ask(query), 0.5)]


if __name__ == "__main__":
    print(AimlBot.XDG_PATH)

    bot = AIMLSolver()
    print(bot.spoken_answer("hello!"))
    print(bot.spoken_answer("Qual é a tua comida favorita?", lang="pt-pt"))
