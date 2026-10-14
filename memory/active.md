# Active Memory

Keep this file short.

## Current Operating Model
AEGIS is the apex agent. Small Markdown files provide durable procedural memory and repeatable skills.

## Current Principle
Objective → perception → planning → execution → verification → learning.

## Selected inference model

2026-10-09: The operator wants AEGIS to use the Qwen model uploaded to AWS: `HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF`. This supersedes the assumption that the workstation's Qwen3.5-9B is the intended study model. S3 objects are present, but the AWS control plane reports zero loaded models. The proposed separate GPU worker is not deployed; its G/VT quota is currently zero. See `deploy/aws/qwen-inference-plan.md`. Resume the ICT 2022 study after successful inference; do not claim that saving weights deploys a model.

Chat safeguards are deployed to the existing AWS control plane: `/chat` HTTP 200, Q4_K_P alias pinned, OpenAI inference disabled and direct external opt-in rejected. Both services are healthy but model readiness is false. Additional GPU spend/quota approval is still pending; no successful Qwen response or completed ICT study is established.

## Maintenance

2026-10-11: With operator approval, installed official llama.cpp b11429 and tested local Qwen3.5-0.8B Q4_0/Q8_0. Q4 chat runs at localhost:8081 (transient user service `aegis-local-qwen`), but failed arithmetic; Q8 passed two checks but incurred heavy paging and 101–152 s replies, so its service was stopped. Neither replaces the selected AWS 27B model or validates autonomous ICT study. See `docs/local-qwen.md` for evidence, limitations and stop/start commands.

Promote only high-value durable facts here. Move stale material to archive.
