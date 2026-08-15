# Remote Model Roster

Last updated: 2026-08-15 (Asia/Bangkok)

Both native Ollama (`/api/tags`, `/api/ps`, `/api/embed`) and OpenAI-compatible (`/v1/models`, chat through Hermes) surfaces are live. Hermes 0.20.0 uses fresh one-shot sessions via `hermes -z`, per-invocation `--model`/`--provider`, and the custom `/v1` endpoint with `chat_completions`. Credentials are stored outside the repository and omitted here.

| Exact model ID | Class | Hermes / tool behavior | Reasoning | Observed behavior | Best role / cautions |
|---|---|---|---|---|---|
| `qwen3.5:122b-a10b` | PRIMARY (restricted) | Hermes-compatible; used 21 tool/API turns read-only and made no edits | Advertised thinking | Completed a cross-module audit but consumed ~972k tokens, invented a test result, and asserted a pragma was missing when present | Difficult second opinions only, with very narrow evidence requests and hard bounds; never self-certifying |
| `devstral-2:123b-instruct-2512-q4_K_M` | PRIMARY | Catalog/tool compatible; implementation trial pending | No advertised thinking; use none | 74.9 GB artifact; not loaded solely for benchmarking | Bounded multi-file implementation after Codex diagnosis; one writer; independent review mandatory |
| `qwen3.6:35b-a3b` | SECONDARY / PRIMARY GENERATION | Hermes one-shot and product Ask verified | Advertised thinking; product can explicitly request `none` | Correct grounded Vietnamese legal answers and semantic paraphrases. Default hidden reasoning could consume a response cap with no visible text; persisted `reasoning_effort: none` removed that failure. Warm direct probe was sub-second; final evidence-rich UI answers were usually about 8–25 s. | Fast diagnosis, verification, moderate implementation, and MVP answer generation; use bounded context and disable hidden reasoning for this UI |
| `qwen3-coder-next:latest` | SECONDARY | Prior bounded Hermes repository/tool task verified under `chat_completions` | No advertised thinking | Concise tool use, but previously overstated conclusions and unsupported test claims | Narrow/mechanical edits and targeted tests; evidence must be reproduced |
| `glm-4.7-flash:latest` | FALLBACK | Hermes exact-response smoke previously verified; tools advertised | Advertised thinking | ~13 s while resident in prior smoke | Fast critic/reviewer and alternate diagnosis; repository tool quality still lightly sampled |
| `qwen3-vl:30b` | SECONDARY (VISION) | Endpoint compatible; tools/vision advertised | Advertised thinking | Catalog verified; not separately invoked in the final visual pass because deterministic browser/DOM checks and local screenshots were sufficient | Screenshot, responsive UI, OCR/page/citation visual review when visual ambiguity remains; supplemental only |
| `bge-m3:567m-fp16` | PRIMARY RUNTIME | Embedding-only, not a chat worker | N/A | 1024 dims, 8192 context; 6/6 Vietnamese legal queries rank 1; 4.725 s live two-text request; exact digest persisted; real DOCX produced 16 searchable vectors | Runtime default for legal retrieval; native API rejects truncation and validates dimensions |
| `nomic-embed-text-v2-moe:latest` | FALLBACK RUNTIME | Embedding-only, not a chat worker | N/A | 768 dims, 512 context; 6/6 rank 1; 3.02 s cold batch | Faster alternate, but short context risks truncating legal chunks |

## Live catalog metadata

| Model | Artifact size | Parameters / quantization | Context | Embedding | Ollama capabilities |
|---|---:|---|---:|---:|---|
| `qwen3.5:122b-a10b` | 81,370,036,360 B | 125.1B / Q4_K_M | 262,144 | 3,072 | vision, completion, tools, thinking |
| `devstral-2:123b-instruct-2512-q4_K_M` | 74,897,651,260 B | 125.0B / Q4_K_M | 262,144 | 12,288 | completion, tools |
| `qwen3.6:35b-a3b` | 23,938,333,577 B | 36.0B / Q4_K_M | 262,144 | 2,048 | vision, completion, tools, thinking |
| `qwen3-coder-next:latest` | 51,741,611,823 B | 79.7B / Q4_K_M | 262,144 | 2,048 | completion, tools |
| `glm-4.7-flash:latest` | 19,019,270,897 B | 29.9B / Q4_K_M | 202,752 | 2,048 | completion, tools, thinking |
| `qwen3-vl:30b` | 19,595,410,062 B | 31.1B / Q4_K_M | 262,144 | 2,048 | vision, completion, tools, thinking |
| `bge-m3:567m-fp16` | 1,157,672,605 B | 566.70M / F16 | 8,192 | 1,024 | embedding |
| `nomic-embed-text-v2-moe:latest` | 957,680,763 B | 475.29M / F16 | 512 | 768 | embedding |

## Scheduling discipline

- One 75–86 GB worker at a time; inspect `/api/ps` first and let keep-alives expire rather than thrash.
- Prefer 32K–64K effective task context. The qwen3.5 audit demonstrated that a broad repository prompt can defeat this intent, so use file/function-bounded prompts.
- Use fresh one-shot sessions per issue. Stop workers that loop, broaden scope, or make unverified claims.
- Embedding and vision models may coexist when server memory permits.
- Implementers never certify their own changes.
