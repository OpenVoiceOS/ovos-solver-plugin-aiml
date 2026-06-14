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

AIML brain files are stored under `ovos_solver_aiml_plugin/aiml_data/<lang>/`
(bundled) or `~/.local/share/aiml/<lang>/` (user-supplied).  When a requested
language has no local brain, the plugin falls back to `en-us`.

### Opt-in brain-file translation (`enable_tx`)

Set `enable_tx: true` in the plugin config to enable automatic translation of
the bundled `en-us` AIML brain into the target language.  This is **off by
default**.

```json
{
  "ovos-solver-aiml-plugin": {
    "lang": "pt-pt",
    "enable_tx": true,
    "translate_plugin": "ovos-translate-plugin-server"
  }
}
```

When enabled and a non-English language is requested that has no local brain:

1. The en-us AIML files are translated using the configured `translate_plugin`
   (default: `ovos-translate-plugin-server`).
2. Only human-readable text inside `<pattern>` and `<template>` nodes is
   translated; AIML structural tags, `<srai>`, `<star>`, `<bot>` tags,
   wildcards (`*` / `_`), and all XML attributes are left untouched.
3. The translated `.aiml` files are written to `~/.local/share/aiml/<lang>/`
   and loaded from there on subsequent runs (translation runs once, then cached).
4. If the translator cannot be loaded or translation fails, the plugin falls
   back gracefully to the `en-us` brain — it never raises.

**Translator plugin note:** translation plugins are instantiated at plugin
load time (not just on first use), so local model-based plugins carry their
full model-load cost each time the engine is created.  A remote translate
plugin such as `ovos-translate-plugin-server` is recommended so that the cost
is paid only when translation is actually needed.

## Contributing intents (OVOS locale)

Conversation content lives in `ovos_solver_aiml_plugin/locale/<lang>/` as
paired `.intent` / `.dialog` files — one file per conversational exchange.
This is the source of truth; the AIML brain is regenerated from it automatically
on every merge to `dev`.

To add or edit responses you only need to touch `locale/` — no AIML knowledge
required.

```
locale/en-us/
├── hello.intent      # trigger utterances (one per line)
├── hello.dialog      # bot responses (one per line, picked at random)
├── favorite_color.intent
└── favorite_color.dialog
```

Full contributor guides:

- **[docs/locale.md](docs/locale.md)** — locale format, `{query}` slots, adding
  intents, translating, the regenerate-on-merge CI flow, and what the converter
  supports vs. skips.
- **[docs/converters.md](docs/converters.md)** — usage of `brain_to_locale.py`
  and `locale_to_brain.py`, examples, the round-trip, and the ~42 % conversion
  rate caveat.
