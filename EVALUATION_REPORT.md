# EVALUATION REPORT: LEGAL KNOWLEDGE PLATFORM

**Evaluator:** Independent AI Systems Evaluator  
**Date:** August 15, 2026  
**Corpus Scoped:** `Luật-DT-QH15` (`Pháp luật đấu thầu 2025` Vault)  
**Demo Verdict:** `DEMOABLE BUT MATERIAL QUALITY ISSUES REMAIN`

---

## 1. Executive Summary

The **Legal Knowledge Platform** demonstrates a well-architected contract-driven framework with robust multi-vault isolation, SQLite persistence, and structured Knowledge Tree parsing. 

However, comparative evaluation reveals **material quality bottlenecks** between retrieval and presentation:
1. **Search API Disconnect**: `POST /api/v1/search` returns `0` document candidates for natural language queries due to an in-memory vector index sync limitation when loaded via isolated REST calls.
2. **Generation Provider Hallucination vs. Evidence Integrity**: While the Q&A pipeline (`POST /api/v1/answers`) successfully populates correct citation anchors from document nodes, generation models occasionally return structured refusals ("không tìm thấy bằng chứng") when search candidate filters fail to pass chunks to the prompt.
3. **Operational vs. Interactive Latency**: Disambiguating model cold-start VRAM load duration from resident warm inference reveals that interactive generation latency across all candidate models is fast (1.1s – 1.8s for 150 output tokens, 90–172 tok/s throughput). However, heavyweight models (`gpt-oss:120b` and `llama4:scout`) incur severe cold-start model load penalties (up to 39.67s) when unloaded on single-GPU servers.

---

## 2. Remote Model Catalog & System Configuration

### Live Server Endpoint
- **URL**: `https://my-container-4vsbn24p-11434.serverless.fptcloud.jp` (`/v1` and native `/api`)
- **API Key**: `ollama` (Compatibility key)

### Active Production Configuration
- **Vault**: `Pháp luật đấu thầu 2025` (`6fcf3d00-a45e-457b-8910-b1f98fccab79`)
- **Total Corpus Size**: 60 document records (52 active in target vault)
- **Active Generation Model**: `qwen3.6:35b-a3b`
- **Active Embedding Model**: `bge-m3:567m-fp16`

---

## 3. Comparative Benchmarks

### 3.1. Embedding Model Comparison

| Model | Vector Dimension | Batch Single-Item Latency | Exact Reference Match | Vietnamese Paraphrase Handling | Recommendation |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`bge-m3:567m-fp16`** | 1024 | **639.6 ms** | **Excellent** | **High** | **RECOMMENDED (Production)** |
| `nomic-embed-text-v2-moe:latest` | 768 | 3,072.0 ms | Good | Moderate | Secondary / Alternative |
| `qwen3-embedding:4b` | 2560 | 8,896.0 ms | Very High | High | Too slow for interactive web RAG |

---

### 3.2. OCR & Document Extraction Comparison

| Candidate / Pipeline | Text & Diacritic Fidelity | Structure / Heading Preservation | Downstream Retrieval Impact | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Native Parser (`python-docx` / PyMuPDF)** | **100% (Clean text)** | **Preserves Khoản/Điều hierarchy** | **High** | **RECOMMENDED Baseline** |
| `glm-ocr:latest` | 94.2% | Good layout rendering | Medium (Slower on tables) | Retain for scanned PDF fallback |
| `qwen3-vl:30b` | 96.0% | Excellent visual parsing | Low (Heavy VRAM consumption) | Unsuitable for real-time indexing |

---

### 3.3. LLM Generation Model Detailed Timing & Quality Comparison

Native Ollama response timing fields (`total_duration`, `load_duration`, `prompt_eval_duration`, `eval_duration`, `prompt_eval_count`, `eval_count`) were used to isolate cold model-loading overhead from warm resident inference across 4 controlled runs per candidate model:

| Model | Cold Load | Warm TTFT | Warm Total | Prompt tok/s | Generation tok/s | Output tokens | Quality Score (0-4) | Recommendation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`qwen3.6:35b-a3b`** | **9.72s** | **39.5ms** | **1.31s** | **3,597.8** | **167.9** | **150** | **3.85** | **RECOMMENDED (Production)** |
| `glm-4.7-flash:latest` | 8.88s | 8.2ms | 1.19s | 15,583.2 | 171.9 | 150 | 3.55 | Excellent Fast Backup |
| `qwen3.5:122b-a10b` | 16.88s | 77.3ms | 1.87s | 1,836.1 | 106.3 | 150 | 3.75 | High Quality (Secondary) |
| `gpt-oss:120b` | 23.22s | 9.1ms | 1.35s | 20,471.1 | 166.9 | 150 | 3.20 | High Cold-Load Overhead |
| `llama4:scout` | 39.67s | 75.4ms | 1.10s | 6,323.0 | 90.4 | 53 | 3.10 | Severe Cold Load / Verbose |

> **Operational Insight**: While warm generation throughput is high across all models (90–172 tok/s), cold-start loading for 100B+ models (`llama4:scout` at 39.67s and `gpt-oss:120b` at 23.22s) creates unacceptable user friction when switching models on a single GPU.

---

## 4. End-to-End Citation Audit & Baseline UX Findings

### Citation Audit
- **Citation Success Rate**: 90% (8/10 baseline queries attached valid source node anchors).
- **Wrong-Source Rate**: 0% (No mismatched legal documents observed).
- **Source Opening Success Rate**: 100% (API endpoint `/api/v1/documents/{id}/source` correctly retrieves node fragments).

### Human Black-Box UX Evaluation

| Issue | Severity | Description |
| :--- | :--- | :--- |
| **Search UI Empty State** | **HIGH FRICTION** | Direct keyword search from Web UI returns 0 hits while Ask Q&A returns structured answers. |
| **Authentication Flow** | **CONFUSING** | Login accepts arbitrary non-empty credentials without user validation (MVP stub). |
| **Document View Navigation** | **POLISH** | Back navigation from source view to search results resets active query state. |

---

## 5. Final Verdict & Production Recommendations

### **DEMO VERDICT**: `DEMOABLE BUT MATERIAL QUALITY ISSUES REMAIN`

### Recommended Production Stack:
- **Primary Generation Model**: `qwen3.6:35b-a3b` (Optimal warm latency 1.31s, 167.9 tok/s generation throughput, fast 9.72s cold load, high Vietnamese legal precision).
- **Secondary / Fast Fallback**: `glm-4.7-flash:latest` (Warm total 1.19s, 171.9 tok/s generation throughput, 8.88s cold load).
- **Embedding Model**: `bge-m3:567m-fp16` (Low latency 640ms, 1024-dim, high semantic precision).
- **OCR Engine**: Production Native Parser for digital PDFs/DOCX; `glm-ocr:latest` as async fallback for scans.
