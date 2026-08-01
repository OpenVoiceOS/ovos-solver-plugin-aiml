# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/robot.svg' card_color='#40DBB0' width='50' height='50' style='vertical-align:bottom'/> AIML Chatbot

An [OVOS](https://github.com/OpenVoiceOS) question solver plugin that answers with an AIML chatbot. It uses the [Alice chatbot](https://www.chatbots.org/chatbot/a.l.i.c.e/) brain to hold open-ended conversation. It answers utterances that no other skill or solver handles, so most utterances get some response.

## Examples

* "Do you like ice cream"
* "Do you like dogs"
* "I have a jump rope"

## Install

```bash
pip install ovos-solver-aiml-plugin
```

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

Set `enable_tx: true` in the plugin config to answer non-English queries. The plugin translates the user utterance into the brain language (English), answers it, then translates the answer back.

This is off by default, so a plain install needs no translate plugin and English deployments pay no extra cost.

```json
{
  "ovos-solver-aiml-plugin": {
    "lang": "pt-pt",
    "enable_tx": true,
    "translate_plugin": "ovos-translate-plugin-server"
  }
}
```

The plugin loads the translator lazily, on the first non-English turn. If the
translator fails to load, or a translation fails, the plugin answers in the
original text instead of raising an error.

**Translator plugin note:** translation agents tend to be instantiated
repeatedly, so a local model-based translate plugin pays its full model-load
cost each time. Use a remote translate service, such as
[ovos-translate-plugin-server](https://github.com/OpenVoiceOS/ovos-translate-plugin-server).

## Converter scripts

The bundled `aiml_data/<lang>/*.aiml` files are the brain. The helper scripts
in `scripts/` are an optional convenience for authoring or inspecting content
in OVOS notation. They are not part of the runtime and not wired into CI:

- `brain_to_locale.py`: exports the cleanly-mappable subset of an AIML or
  RiveScript brain to paired `.intent` / `.dialog` files (`{query}` slot for
  wildcards).
- `locale_to_brain.py`: the reverse. It regenerates a brain from such files.

The conversion is deliberately partial. Entries that rely on constructs with
no direct OVOS equivalent (`<srai>`, `<condition>`, `<star>`, topic state, and
so on) are skipped, and exports never emit residual `<…>` markup. See
[docs/converters.md](docs/converters.md).

## Related projects

- [OpenVoiceOS/ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager): loads this plugin through the `opm.agents.chat` entry point.
- [OpenVoiceOS/ovos-translate-plugin-server](https://github.com/OpenVoiceOS/ovos-translate-plugin-server): recommended remote translate plugin for `enable_tx`.

## License

[Apache License 2.0](LICENSE)
