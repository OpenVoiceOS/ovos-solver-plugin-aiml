# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/robot.svg' card_color='#40DBB0' width='50' height='50' style='vertical-align:bottom'/> AIML Chatbot
 
Give Mycroft some sass with AIML!

Leverages the [Alice chatbot](https://www.chatbots.org/chatbot/a.l.i.c.e/) to create some fun interactions.  Phrases not explicitly handled by other skills will be run by the chatbot, so nearly every interaction will have _some_ response.  But be warned, Mycroft might become a bit obnoxious...

## Examples 
* "Do you like ice cream"
* "Do you like dogs"
* "I have a jump rope"


## Usage

```python
from ovos_solver_aiml_plugin import AIMLChatEngine
from ovos_plugin_manager.templates.agents import AgentMessage, MessageRole

engine = AIMLChatEngine({"lang": "en-us"})
reply = engine.continue_chat([AgentMessage(role=MessageRole.USER, content="hello")])
print(reply.content)
# Hi there!
```

## Language support

The bundled AIML brain is English. Brain files live under
`ovos_solver_aiml_plugin/aiml_data/<lang>/` (bundled) or
`~/.local/share/aiml/<lang>/` (user-supplied).

### Opt-in query translation (`enable_tx`)

Set `enable_tx: true` in the plugin config to answer non-English queries: the
user utterance is translated into the brain language (English), answered, and
the answer translated back. This is **off by default** — a plain install
depends on no translate plugin and English deployments pay nothing.

```json
{
  "ovos-solver-aiml-plugin": {
    "lang": "pt-pt",
    "enable_tx": true,
    "translate_plugin": "ovos-translate-plugin-server"
  }
}
```

The translator is loaded lazily on the first non-English turn. If it cannot be
loaded or a translation fails, the plugin degrades gracefully to answering in
the original text — it never raises.

**Translator plugin note:** translation agents tend to be instantiated
repeatedly, so a local model-based translate plugin would carry its full
model-load cost each time. A **remote** translate service such as
`ovos-translate-plugin-server` is strongly recommended.

## Converter scripts

The bundled `aiml_data/<lang>/*.aiml` files are the brain. The helper scripts in
`scripts/` are an **optional** convenience for authoring/inspecting content in
OVOS notation — they are not part of the runtime and not wired into CI:

- `brain_to_locale.py` — export the cleanly-mappable subset of an AIML/RiveScript
  brain to paired `.intent` / `.dialog` files (`{query}` slot for wildcards).
- `locale_to_brain.py` — the reverse, regenerating a brain from such files.

The conversion is deliberately partial: entries relying on constructs with no
direct OVOS equivalent (`<srai>`, `<condition>`, `<star>`, topic state, …) are
skipped, and exports never emit residual `<…>` markup. See
[docs/converters.md](docs/converters.md).
