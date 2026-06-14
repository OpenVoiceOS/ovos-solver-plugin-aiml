#!/usr/bin/env python3
"""Partial converter: AIML / RiveScript brains -> OVOS ``locale/`` resources.

Each AIML ``<category>`` (or RiveScript ``+ trigger`` / ``- response`` pair) becomes
one OVOS intent: a ``<name>.intent`` file holding the trigger utterance(s) and a
``<name>.dialog`` file holding the response(s). This preserves the question->answer
mapping (merging every pattern into one file would lose it).

It is deliberately PARTIAL — it converts the cleanly-mappable subset and *skips*
(reporting them) categories/triggers that rely on constructs with no direct OVOS
equivalent: AIML ``<srai>``/``<condition>``/``<random>``/``<star>`` templates, topic
state; RiveScript ``%`` previous, ``@`` redirects, ``{topic}``, ``<call>``, arrays.
Wildcards (AIML ``*``, RiveScript ``*``/``_``) become a single ``{query}`` slot.

Usage:
    brain_to_locale.py aiml <aiml_dir> <out_locale_dir>
    brain_to_locale.py rivescript <rive_dir> <out_locale_dir>
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

# template/response constructs we can't faithfully map -> skip the whole entry
_AIML_COMPLEX = ("<srai", "<random", "<condition", "<star", "<get", "<that", "<topic")
_RIVE_COMPLEX = ("<call>", "@", "{topic}", "<input", "<reply", "(@")


def _slug(text, used):
    """A unique, filesystem-safe base name derived from the trigger text."""
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "intent"
    name, i = s, 1
    while name in used:
        i += 1
        name = f"{s}_{i}"
    used.add(name)
    return name


def _write_pair(out_dir, name, utterances, responses):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, name + ".intent"), "w", encoding="utf-8") as f:
        f.write("\n".join(utterances) + "\n")
    with open(os.path.join(out_dir, name + ".dialog"), "w", encoding="utf-8") as f:
        f.write("\n".join(responses) + "\n")


def _pattern_to_intent(pattern):
    """AIML/RiveScript pattern -> an OVOS Padatious utterance line."""
    line = pattern.strip().lower()
    # collapse wildcards (* _) into one named slot
    line = re.sub(r"[\*_]+", "{query}", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def convert_aiml(src_dir, out_dir):
    used, kept, skipped = set(), 0, 0
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith(".aiml"):
            continue
        try:
            root = ET.parse(os.path.join(src_dir, fn)).getroot()
        except ET.ParseError:
            continue
        for cat in root.iter("category"):
            pat_el, tpl_el = cat.find("pattern"), cat.find("template")
            if pat_el is None or tpl_el is None:
                skipped += 1
                continue
            raw_tpl = ET.tostring(tpl_el, encoding="unicode")
            # skip templates that depend on unmappable constructs
            if any(tag in raw_tpl for tag in _AIML_COMPLEX):
                skipped += 1
                continue
            pattern = "".join(pat_el.itertext()).strip()
            # template text = visible text only (drops <bot/>, <think/>, <set/>…)
            response = re.sub(r"\s+", " ", "".join(tpl_el.itertext())).strip()
            if not pattern or not response:
                skipped += 1
                continue
            utt = _pattern_to_intent(pattern)
            _write_pair(out_dir, _slug(pattern, used), [utt], [response])
            kept += 1
    return kept, skipped


def convert_rivescript(src_dir, out_dir):
    used, kept, skipped = set(), 0, 0
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith(".rive"):
            continue
        trigger, responses = None, []

        def _clean_response(r):
            """Map a single <star>/<star1> to {query}; reject anything else."""
            r = r.replace("<star1>", "<star>").replace("<star>", "{query}")
            # remaining angle-bracket tags or {…} blocks can't be mapped 1:1
            if re.search(r"<[^>]+>|\{(?!query\}).+?\}", r):
                return None
            return r

        def flush():
            nonlocal trigger, responses, kept, skipped
            if trigger is not None:
                cleaned = [_clean_response(r) for r in responses]
                ok = (responses and all(c is not None for c in cleaned)
                      and not any(c in trigger for c in _RIVE_COMPLEX))
                if ok:
                    _write_pair(out_dir, _slug(trigger, used),
                                [_pattern_to_intent(trigger)], cleaned)
                    kept += 1
                elif responses:
                    skipped += 1
            trigger, responses = None, []

        with open(os.path.join(src_dir, fn), encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                s = line.strip()
                if not s or s.startswith(("//", "/*", "*", "!", ">", "<")):
                    continue
                if s.startswith("+ "):      # new trigger -> flush previous
                    flush()
                    trigger = s[2:].strip()
                elif s.startswith("- "):     # response
                    responses.append(s[2:].strip())
                elif s.startswith("^ ") and trigger is not None and not responses:
                    trigger += " " + s[2:].strip()   # trigger continuation
                else:
                    flush()                  # %, @, * conditionals etc. -> break pair
            flush()
    return kept, skipped


def main(argv):
    if len(argv) != 4 or argv[1] not in ("aiml", "rivescript"):
        print(__doc__)
        return 2
    fmt, src, out = argv[1], argv[2], argv[3]
    kept, skipped = (convert_aiml if fmt == "aiml" else convert_rivescript)(src, out)
    total = kept + skipped
    pct = (100 * kept // total) if total else 0
    print(f"{fmt}: converted {kept}/{total} entries ({pct}%), skipped {skipped} "
          f"(unmappable constructs) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
