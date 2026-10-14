# Local Qwen trial

## STATUS / OBJECTIVE

Installed and tested on 2026-10-11. Q4_0 local chat works, but accuracy and speed are limited. Q8_0 was more accurate on these checks but much slower with heavy paging. Neither is validated as AEGIS's main autonomous model. This is not the uploaded 27B model.

## ACTION / CHANGES

- Installed official CPU release: https://github.com/ggml-org/llama.cpp/releases/tag/b11429, version `0.6.0-dev`, commit `d81235049`, at `~/.local/opt/llama-b11429`.
- Release contains baseline x64/SSE4.2 and newer CPU backends with runtime selection. `llama-server --version` executes successfully on this CPU. Downloads use TLS-verified curl; serving uses an offline local model and loopback HTTP only.
- Source fallback retained at `~/.local/opt/aegis-llama.cpp`, commit `a9d27ac693ff0a1d3cba449c912c2b891904a4c7`, plus isolated CMake 4.4.4 at `~/.local/opt/aegis-llama-build-tools`. Compilation was intentionally interrupted at 14% after finding the compatible official release; it did not complete. No upstream code was modified.
- Model: https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF at revision `8fea620810c4afa23dd6443f999a48574c1611a3`, file `Qwen3.5-0.8B-Q4_0.gguf`, 563,036,064 bytes.
- Weights: `~/.local/share/aegis/models/qwen3.5-0.8b/Qwen3.5-0.8B-Q4_0.gguf`.
- Existing AWS resources, model files, model registry and Compose defaults are unchanged by this trial.

## EVIDENCE / TESTS

The downloaded model SHA-256 matches the publisher's LFS metadata: `57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`.

The downloaded release SHA-256 matches GitHub's asset digest: `f6d25dde8f51133143d1453da4fd5f73b145127177612a283bf7995957af3392`.

Real Q4_0 inference results (short system prompt, thinking disabled):

| Check | Observed answer | Result | Wall time |
| --- | --- | --- | --- |
| 17 + 25, number only | `32` | FAIL; expected 42 | 26.1 s |
| Repeat `LOCAL_QWEN_OK` exactly | `LOCAL_QWEN_OK` | PASS | 37.6 s |
| Extract lesson start time from supplied note | `9:30 AM` in a short sentence | PASS | 40.2 s |

The Q8_0 file (833,592,096 bytes) was also downloaded from the same pinned revision and verified: SHA-256 `37ae482d336108d23516fa35e8e0c4126688d81018b87178a18d752a1357814f`. It answered `42` and extracted `9:30 AM` correctly, but took 101.16 s and 152.19 s respectively. Its service reached a 986,488,832-byte memory peak; `vmstat` showed heavy paging and I/O wait. That service was stopped and Q4_0 restored. These tiny tests are not a general quality benchmark.

`/health` returned `{"status":"ok"}`; `/v1/models` exposed the expected Q4 alias and 2048-token context. Playwright verified HTTP 200, the loaded model label, message textbox and Send button in the bundled browser UI. These UI checks were read-only; real generation was separately verified through the local API. Curl must use `--compressed` for the UI because bundled assets require gzip support. Shell syntax, Python compilation, CLI token limits and clean timeout handling passed. No OpenAI requests were used for inference.

## NEXT / USAGE

The Q4 server was left running as the transient user service `aegis-local-qwen`. Open `http://localhost:8081` on this machine. It does not automatically start on future boots. Check or stop it with:

```bash
systemctl --user status aegis-local-qwen
systemctl --user stop aegis-local-qwen
```

To run it again manually from the repository (after stopping any existing server):

```bash
bash scripts/start_local_qwen.sh
```

Leave that terminal running. In another terminal:

```bash
python3 scripts/ask_local_qwen.py "Explain what a limit order is in two sentences."
```

The test endpoint is `http://127.0.0.1:8081/v1`, model alias `aegis-qwen3.5-0.8b-q4_0`. It binds only to loopback, restricts CORS to localhost and disables built-in agent mode. The transient service caps CPU at 150%, memory at 1200 MiB and swap at 256 MiB. The foreground command does not apply those systemd resource caps. Stop the foreground server with Ctrl+C.

## ISSUES / LIMITS

This is a 0.8B quantized model, not a capability-equivalent substitute for the 27B Qwen. Start with short prompts: context is 2048 tokens, one request at a time, and thinking is disabled. Replies are not proof of autonomous tool execution, ICT mastery or trading reliability. The terminal helper is a direct model chat, not AEGIS's governed orchestration pipeline. No automatic startup or default-model switch was performed. AWS model files and deployed services were untouched. Disk space is low (about 1.6 GiB remaining after installation); both quantizations and the source-build fallback remain on disk.
