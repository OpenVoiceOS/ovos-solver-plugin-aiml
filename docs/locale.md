# OVOS locale/ — Source of Truth for the AIML Brain

`ovos_solver_aiml_plugin/locale/` is the contributor-facing source of truth for
conversation content.  The AIML brain files under `aiml_data/<lang>/generated.aiml`
are **derived artifacts** — they are regenerated automatically from `locale/` on
every merge to `dev` and should not be edited directly.

---

## File format

Each conversational exchange is represented by a **pair** of files sharing the same
base name:

| File | Role |
|------|------|
| `<name>.intent` | One trigger utterance per line (what the user might say) |
| `<name>.dialog` | One response per line (what the bot can answer) |

### Example pair — `hello.intent` / `hello.dialog`

```
# hello.intent
hello
hi
hey there
```

```
# hello.dialog
Hi there!
Hello!
Hey, how are you?
```

Lines starting with `#` are comments and are ignored by the compiler.

---

## The `{query}` slot

When a trigger contains a wildcard (`*` in AIML), it becomes the named slot
`{query}` in the `.intent` file.

| AIML | OVOS locale |
|------|-------------|
| `DO YOU LIKE *` | `do you like {query}` |
| `WHAT IS *` | `what is {query}` |

In the generated AIML the `{query}` slot compiles back to `*` in the
`<pattern>` and to `<star/>` inside the `<template>`:

```xml
<category>
  <pattern>DO YOU LIKE *</pattern>
  <template>I love <star/>!</template>
</category>
```

---

## How to add a new intent

1. Choose a descriptive base name, e.g. `favorite_color`.
2. Create `locale/en-us/favorite_color.intent` with one trigger per line:
   ```
   what is your favorite color
   do you have a favorite color
   which color do you like most
   ```
3. Create `locale/en-us/favorite_color.dialog` with one or more responses:
   ```
   My favorite color is blue.
   I am rather fond of deep violet.
   ```
4. Open a PR to `dev`.  The `regenerate-brain` CI job will compile your new
   intent into `aiml_data/en-us/generated.aiml` automatically after the PR
   merges.

Multiple responses in `.dialog` are emitted as an AIML `<random>` block so the
bot picks one at random each time:

```xml
<template>
  <random>
    <li>My favorite color is blue.</li>
    <li>I am rather fond of deep violet.</li>
  </random>
</template>
```

Multiple utterances in `.intent` produce one canonical AIML category plus
`<srai>` redirects for the alternatives, so they all resolve to the same
template.

---

## How to translate

1. Copy the `locale/en-us/` directory to `locale/<lang>/`
   (e.g. `locale/pt-pt/`).
2. Translate the text in every `.intent` and `.dialog` file into the target
   language.  Keep `{query}` slots exactly as-is — they are engine tokens,
   not human text.
3. Open a PR to `dev`.  The regenerate CI will produce
   `aiml_data/<lang>/generated.aiml` automatically.

You do **not** need to create or edit any AIML XML.

---

## Regenerate-on-merge CI flow

The workflow `.github/workflows/regenerate-brain.yml` runs on every push to
`dev` (i.e. after each PR merge) and on `workflow_dispatch`.

Steps:

1. Check out `dev`.
2. For every `locale/<lang>/` directory, run
   `scripts/locale_to_brain.py aiml locale/<lang> aiml_data/<lang>/generated.aiml`.
3. If `git diff` shows changes under `aiml_data/`, commit and push back to
   `dev` as `JarbasAi <jarbasai@mailfence.com>`.
4. If there are no changes (idempotent second run), exit 0 — no commit, no
   push.

The release workflow (`publish-alpha.yml`) fires on `pull_request[closed]` to
`dev`, not on `push` to `dev`, so the regenerate commit does **not** trigger a
release.

---

## What the converter supports vs. skips

`scripts/brain_to_locale.py` converts the **cleanly-mappable** subset of the
legacy AIML brain (~42 % of categories).  The rest are skipped because they
use constructs with no direct OVOS-locale equivalent.

### Supported

| AIML construct | OVOS equivalent |
|----------------|-----------------|
| `<pattern>` text | `.intent` line |
| `<template>` text | `.dialog` line |
| `*` wildcard in pattern | `{query}` in `.intent` |

### Skipped (reported, not converted)

| AIML construct | Reason skipped |
|----------------|----------------|
| `<srai>` | Redirect to another category — no direct mapping |
| `<random>` | Handled only when the whole template is text; complex nesting skipped |
| `<condition>` | Conditional branching — stateful, no OVOS equivalent |
| `<star/>` in template | Wildcard echo — supported only in simple text templates |
| `<get>` / `<set>` | Variable read/write — stateful |
| `<that>` | Context-dependent matching — stateful |
| `<topic>` | Topic state — stateful |

The unconverted legacy categories remain in the original `aiml_data/en-us/*.aiml`
files and continue to be loaded by the engine alongside `generated.aiml`.  The
locale source of truth expands over time as contributors add new intents.
