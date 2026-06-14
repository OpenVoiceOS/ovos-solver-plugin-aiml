# Converter Scripts

Two stdlib-only Python scripts convert between OVOS `locale/` notation and
brain files.  Neither script requires any third-party dependencies.

---

## `scripts/brain_to_locale.py` — brain → locale (one-time bootstrap)

Converts an existing AIML (or RiveScript) brain into OVOS `locale/` pairs.
Run this once to bootstrap a language from its legacy brain; after that, edit
`locale/` directly and let the CI regenerate the brain.

### Usage

```
python scripts/brain_to_locale.py aiml <aiml_dir> <out_locale_dir>
python scripts/brain_to_locale.py rivescript <rive_dir> <out_locale_dir>
```

### Example

```bash
# Bootstrap en-us locale from the bundled AIML brain
python scripts/brain_to_locale.py aiml \
    ovos_solver_aiml_plugin/aiml_data/en-us \
    ovos_solver_aiml_plugin/locale/en-us
```

Output:
```
aiml: converted 24175/57504 entries (42%), skipped 33329 (unmappable constructs) -> ovos_solver_aiml_plugin/locale/en-us
```

Each converted AIML `<category>` becomes one `.intent` / `.dialog` pair.

---

## `scripts/locale_to_brain.py` — locale → brain (CI / runtime rebuild)

Compiles OVOS `locale/` pairs into a single AIML (or RiveScript) brain file.
This is what the CI job runs after every merge.

### Usage

```
python scripts/locale_to_brain.py aiml <locale_dir> <out.aiml>
python scripts/locale_to_brain.py rivescript <locale_dir> <out.rive>
```

### Example

```bash
# Regenerate en-us brain from locale
python scripts/locale_to_brain.py aiml \
    ovos_solver_aiml_plugin/locale/en-us \
    ovos_solver_aiml_plugin/aiml_data/en-us/generated.aiml
```

Output:
```
aiml: compiled 24175 intents from ovos_solver_aiml_plugin/locale/en-us -> ovos_solver_aiml_plugin/aiml_data/en-us/generated.aiml
```

---

## The round-trip

```
locale/en-us/   ──locale_to_brain──►  aiml_data/en-us/generated.aiml
                                                │
                                      (AIML engine loads this)

aiml_data/en-us/*.aiml  ──brain_to_locale──►  locale/en-us/
(one-time bootstrap only)
```

The round-trip is lossless for the converted subset: running
`brain_to_locale` → `locale_to_brain` on the same entries produces equivalent
AIML (patterns uppercased, responses escaped, multi-response `<random>` blocks
added).  The AIML is not byte-identical to the original because:

- Patterns are normalized to uppercase.
- Template text is XML-escaped (`&amp;`, `&lt;`, `&gt;`).
- Multi-utterance intents use `<srai>` redirects rather than duplicate
  templates.

These differences are semantically equivalent for the AIML interpreter.

---

## Conversion rate caveat (~42 %)

The `brain_to_locale` converter maps only the cleanly-mappable subset of AIML
categories.  Approximately **42 %** of the legacy `en-us` brain maps cleanly;
the remaining **58 %** use constructs (conditional branching, topic state,
`<srai>` chains, variable get/set) that have no direct OVOS-locale equivalent
and are skipped.

The unconverted categories are **not lost** — they remain in the original
`*.aiml` files under `aiml_data/en-us/` and the engine loads all `.aiml` files
in that directory, including both the legacy files and `generated.aiml`.  Over
time, contributors can rewrite complex categories as simple `.intent`/`.dialog`
pairs and grow the locale coverage.

See `docs/locale.md` for the full list of supported vs. skipped constructs.
