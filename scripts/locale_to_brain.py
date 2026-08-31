#!/usr/bin/env python3
"""Build an AIML / RiveScript brain from OVOS ``locale/`` resources.

The reverse of ``brain_to_locale.py``. The contributor-facing source of truth is
OVOS notation — a ``<name>.intent`` file (trigger utterances) paired with a
``<name>.dialog`` file (responses). This compiles those pairs into the brain
format the engine consumes, so users can write/translate in standard OVOS
notation and the brain is regenerated at runtime or on PR merge.

A ``{query}`` slot maps to the engine wildcard (AIML ``*`` / ``<star/>``,
RiveScript ``*`` / ``<star>``). Multiple utterances that share one dialog become
one canonical entry plus redirects (AIML ``<srai>`` / RiveScript ``@``); multiple
responses become a random set (AIML ``<random><li>`` / repeated RiveScript ``-``).

Usage:
    locale_to_brain.py aiml <locale_dir> <out.aiml>
    locale_to_brain.py rivescript <locale_dir> <out.rive>
"""
import os
import re
import sys
from xml.sax.saxutils import escape


def _pairs(locale_dir):
    """Yield (name, [utterances], [responses]) for each .intent/.dialog pair."""
    for fn in sorted(os.listdir(locale_dir)):
        if not fn.endswith(".intent"):
            continue
        name = fn[:-len(".intent")]
        dialog = os.path.join(locale_dir, name + ".dialog")
        if not os.path.isfile(dialog):
            continue
        utts = [l.strip() for l in open(os.path.join(locale_dir, fn), encoding="utf-8")
                if l.strip() and not l.startswith("#")]
        resps = [l.strip() for l in open(dialog, encoding="utf-8")
                 if l.strip() and not l.startswith("#")]
        if utts and resps:
            yield name, utts, resps


def to_aiml(locale_dir, out_path):
    n = 0
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<aiml version="1.0">']
    for _, utts, resps in _pairs(locale_dir):
        patterns = [re.sub(r"\{query\}", "*", u).upper().strip() for u in utts]
        # template: {query} -> <star/>; multiple responses -> <random>
        r = [escape(re.sub(r"\{query\}", "<star/>", x)).replace("&lt;star/&gt;", "<star/>")
             for x in resps]
        if len(r) == 1:
            tpl = r[0]
        else:
            tpl = "<random>" + "".join(f"<li>{x}</li>" for x in r) + "</random>"
        out.append(f"<category><pattern>{patterns[0]}</pattern>")
        out.append(f"<template>{tpl}</template>")
        out.append("</category>")
        for p in patterns[1:]:          # extra utterances redirect to the canonical
            out.append(f"<category><pattern>{p}</pattern><template><srai>{patterns[0]}</srai></template></category>")
        n += 1
    out.append("</aiml>")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return n


def to_rivescript(locale_dir, out_path):
    n = 0
    out = ["! version = 2.0", ""]
    for _, utts, resps in _pairs(locale_dir):
        triggers = [re.sub(r"\{query\}", "*", u).lower().strip() for u in utts]
        out.append(f"+ {triggers[0]}")
        for x in resps:
            resp = re.sub(r"\{query\}", "<star>", x)
            out.append(f"- {resp}")
        out.append("")
        for t in triggers[1:]:          # extra utterances redirect to the canonical
            out.append(f"+ {t}")
            out.append(f"@ {triggers[0]}")
            out.append("")
        n += 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    return n


def main(argv):
    if len(argv) != 4 or argv[1] not in ("aiml", "rivescript"):
        print(__doc__)
        return 2
    fmt, src, out = argv[1], argv[2], argv[3]
    n = (to_aiml if fmt == "aiml" else to_rivescript)(src, out)
    print(f"{fmt}: compiled {n} intents from {src} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
