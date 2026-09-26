# ovos-persona-server serving a persona backed by this plugin's chat engine
# (opm.agents.chat, AIMLChatEngine). No API key or other external credential
# is needed -- AIML pattern matching runs entirely offline against the
# bundled aiml_data.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Prerelease floor: ovos-persona needs a version new enough to resolve a
# chat-engine entry point as a persona handler.
RUN pip install --no-cache-dir "ovos-persona>=0.9.0a9"

# This plugin is installed from PyPI rather than the local checkout, so the
# image always matches whatever release is public -- there is no local
# source dependency to build from here.
#
# Pinned to the 0.0.2 alpha line: the latest stable release on PyPI, 0.0.1,
# predates AIMLChatEngine and the opm.agents.chat entry point entirely (it
# only ships the deprecated QuestionSolver class, which pulls in a hard
# ovos-translate-plugin-server dependency this image does not carry and
# fails to start). Verified against the published wheel: 0.0.2a6 registers
# "opm.agents.chat = ovos_solver_aiml_plugin:AIMLChatEngine"; 0.0.1 does not
# register opm.agents.chat at all.
RUN pip install --no-cache-dir "ovos-solver-aiml-plugin>=0.0.2a6"

# [mcp] mounts the MCP tool endpoint. From 0.17.0a1 that mount is opt-in --
# installing the extra alone no longer flips it on, so --mcp below is
# required, matching ovos-plugin-linguonnx's image.
RUN pip install --no-cache-dir "ovos-persona-server[mcp]>=0.17.0a1"

# The persona JSON: "handlers" (the modern config key; "solvers" is kept as
# a legacy alias) points at this plugin by its opm.agents.chat id.
RUN mkdir -p /personas && printf '%s\n' \
    '{' \
    '  "name": "AimlBot",' \
    '  "handlers": ["ovos-solver-aiml-plugin"]' \
    '}' > /personas/aimlbot.json

EXPOSE 8337

ENTRYPOINT ["ovos-persona-server", "--personas-dir", "/personas", "--mcp", \
            "--port", "8337", "--host", "0.0.0.0"]
