import os
import random
import time
from datetime import date
from os import listdir, remove as remove_file, makedirs
from os.path import dirname, isfile

from neon_solvers import AbstractSolver
from ovos_utils.log import LOG
from ovos_utils.xdg_utils import xdg_data_home

# patch so en-us works with python > 3.7
time.clock = time.perf_counter
import aiml


class AimlBot:

    def __init__(self, lang="en-us", settings=None):
        self.settings = settings or {}
        self.lang = lang
        self.kernel = aiml.Kernel()
        xdg_aiml = os.path.join(xdg_data_home(), "aiml", lang)
        makedirs(xdg_aiml, exist_ok=True)
        self.aiml_path = os.path.join(dirname(__file__), "aiml", lang)
        self.brain_path = os.path.join(xdg_aiml, "bot_brain.brn")
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
        self.speak_dialog("reset.memory")
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
            asked_question = False
            if answer.endswith("?"):
                asked_question = True
            return answer

    def shutdown(self):
        if self.brain_loaded:
            self.kernel.saveBrain(self.brain_path)
            self.kernel.resetBrain()  # Manual remove


class AIMLSolver(AbstractSolver):
    def __init__(self):
        super().__init__(name="AIML")
        self.brain = AimlBot()
        self.brain.load_brain()

    # officially exported Solver methods
    def get_spoken_answer(self, query, context=None):
        return self.brain.ask_brain(query)


if __name__ == "__main__":
    bot = AIMLSolver()
    print(bot.spoken_answer("hello!"))
    print(bot.spoken_answer("Olá!", {"lang": "pt-pt"}))


