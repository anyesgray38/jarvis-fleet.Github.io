# OpenAI Agents API research runner

`run_openai_research_agent.sh` creates a reusable `New agent` definition in
the project configured by `OPENAI_PROJECT_ID` or `deploy/.env`, then starts a
streamed session using the returned agent ID.

The agent uses GPT-6 Astra and hosted live web search. Sessions default to the
OpenAI-hosted runtime (`environment: {"type": "openai_hosted"}`), so no local
executor is required. Set `OPENAI_AGENT_ENVIRONMENT=none` for a text-and-tool
session that does not need a sandbox.

The runner reads `OPENAI_API_KEY` from `deploy/.env`, sends the project ID in
`OpenAI-Project`, and never prints the key. The key needs the Agents API
permissions documented by OpenAI: `api.agents.read`, `api.agents.write`, and
`api.responses.write`.

Run it from the repository root:

```bash
bash agents/run_openai_research_agent.sh "Research current OpenAI Agents API web-search guidance and summarize it with sources."
```

You can also override the project or environment file for a run:

```bash
OPENAI_PROJECT_ID=proj_pHyP61mVdJm7ZhODMpglh2wI \
AEGIS_ENV_FILE=/absolute/path/to/.env \
bash agents/run_openai_research_agent.sh "Your research request"
```

To make an OpenAI Files upload available inside the hosted session, pass its
file ID. The runner materializes it under `/workspace/input/research.md` in
the OpenAI-hosted environment; it is not copied back to this machine:

```bash
OPENAI_INPUT_FILE_ID=file-... \
bash agents/run_openai_research_agent.sh "Summarize the uploaded research source."
```

The output includes the reusable `agent_id`, streamed event names, streamed
text, tool-call events, errors, and the resulting `session_id`.

To retry a session with an existing definition without creating another agent:

```bash
OPENAI_AGENT_ID=agent_959c34209a9c485a8e6fa5b6284786420efd6676d2b74ed29a \
bash agents/run_openai_research_agent.sh "Give a concise overview of the OpenAI Agents API."
```
