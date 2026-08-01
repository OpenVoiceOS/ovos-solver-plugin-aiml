# Converter Scripts

Two stdlib-only Python scripts convert between OVOS `.intent` / `.dialog` notation and brain files. They are optional standalone helpers for authoring or inspecting content in OVOS notation.

The plugin does not import them, and CI does not run them. The bundled `aiml_data/<lang>/*.aiml` files remain the brain.

## `scripts/brain_to_locale.py`: brain to OVOS notation

This script exports the cleanly-mappable subset of an AIML (or RiveScript)
brain to paired `.intent` / `.dialog` files.

```
python scripts/brain_to_locale.py aiml <aiml_dir> <out_dir>
python scripts/brain_to_locale.py rivescript <rive_dir> <out_dir>
```

Each converted AIML `<category>` (or RiveScript trigger/response pair)
becomes one `.intent` / `.dialog` pair. Wildcards collapse to a single
`{query}` slot.

Exports never contain residual `<…>` markup. The script skips any entry whose
pattern or response still carries AIML or RiveScript markup, instead of
emitting it with broken tags.

## `scripts/locale_to_brain.py`: OVOS notation to brain

This script reverses the process: it compiles `.intent` / `.dialog` pairs
into a single AIML (or RiveScript) brain file.

```
python scripts/locale_to_brain.py aiml <in_dir> <out.aiml>
python scripts/locale_to_brain.py rivescript <in_dir> <out.rive>
```

## Partial by design

The conversion maps only the cleanly-mappable subset. Constructs with no direct OVOS equivalent get reported and skipped. These include AIML `<srai>`, `<condition>`, `<random>`, `<star>`, and topic state, plus RiveScript redirects, `{topic}`, and arrays.

The round trip (`brain_to_locale` then `locale_to_brain`) stays semantically equivalent for the converted subset. Patterns become uppercase and responses get XML-escaped.

---
[Home](../README.md)
