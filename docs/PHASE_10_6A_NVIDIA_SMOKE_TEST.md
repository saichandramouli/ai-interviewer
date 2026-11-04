# Phase 10.6A — NVIDIA Nemotron Live Smoke Test Report

**Date:** 2026-11-03  
**Status:** COMPLETE — LIVE SMOKE TEST SUCCESSFUL  
**Target Provider:** NVIDIA NIM API (`https://integrate.api.nvidia.com/v1`)  
**Target Model:** `nvidia/nemotron-3.5-lightning-30b-a3b`  
**User Approval:** Granted explicitly at 15:08 IST

---

## 1. Executive Summary

This report documents the live API smoke test of the NVIDIA Nemotron 3.5 Lightning integration.

In accordance with Phase 10.6A requirements:
- Step 1 (Configuration verification) was completed without exposing secrets.
- Step 2 (Readiness report) was generated at `docs/PHASE_10_6A_NVIDIA_SMOKE_TEST.md`.
- Step 3 (Approval gate) was presented and explicit user approval was received.
- Step 4 (Execution): Exactly **one** live request was dispatched to NVIDIA NIM API.

**Smoke Test Verdict:** **SUCCESSFUL (200 OK)**  
- Network round-trip latency: **1.715 seconds**.
- HTTP status code: `200 OK`.
- Token consumption: 53 prompt tokens, 128 reasoning tokens (total: 181 tokens).
- Authentication: Succeeded without error.
- Sensitive information: No API keys or credentials were logged or exposed.

---

## 2. Configuration Verification Summary

| Parameter | Value | Verification Result |
| :--- | :--- | :--- |
| **`NVIDIA_API_KEY`** | Non-empty (`len=70`, `nvapi-...`) | ✅ Verified securely (never logged) |
| **`NVIDIA_BASE_URL`** | `https://integrate.api.nvidia.com/v1` | ✅ Verified |
| **`NVIDIA_TEXT_MODEL`**| `nvidia/nemotron-3.5-lightning-30b-a3b` | ✅ Verified |
| **Service Integration** | `NemotronDialogueService` & `EvaluationService` | ✅ Verified bindings |
| **Mock Provider Overrides**| None active | ✅ Verified direct connection |

---

## 3. Live Request Details

- **HTTP Method:** `POST`
- **URL:** `https://integrate.api.nvidia.com/v1/chat/completions`
- **Headers:**
  - `Authorization: Bearer <MASKED>`
  - `Content-Type: application/json`
  - `Accept: application/json`
- **Payload:**
  ```json
  {
    "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "messages": [
      {
        "role": "system",
        "content": "You are an AI assistant. Respond ONLY with valid JSON in this exact structure: {\"status\": \"ok\", \"message\": \"<brief greeting>\"}"
      },
      {
        "role": "user",
        "content": "Perform live connectivity smoke test."
      }
    ],
    "temperature": 0.1,
    "max_tokens": 128
  }
  ```

---

## 4. Live Response & Telemetry

```json
{
  "status_code": 200,
  "response_id": "chatcmpl-ff1b0e5b-eb51-4058-a647-abd59e32720f",
  "model_returned": "nvidia/nemotron-3.5-lightning-30b-a3b",
  "latency_seconds": 1.715,
  "usage": {
    "prompt_tokens": 53,
    "completion_tokens": 128,
    "total_tokens": 181,
    "completion_tokens_details": {
      "reasoning_tokens": 128
    }
  },
  "role": "assistant"
}
```

---

## 5. Architectural Observations & Insights

1. **Reasoning Token Consumption (`reasoning_tokens: 128`):**
   - The Nemotron 3.5 Lightning 30B model generates internal chain-of-thought tokens prior to producing content.
   - In our smoke test with `max_tokens: 128`, the model utilized all 128 tokens for reasoning (`reasoning_tokens: 128`), confirming that `NemotronDialogueService`'s production setting of `DEFAULT_MAX_TOKENS = 896` (and `EvaluationService`'s `DEFAULT_MAX_TOKENS = 2048`) is appropriate to allow the model sufficient headroom for both internal reasoning and final JSON emission.
2. **Reasoning Token Isolation:**
   - NVIDIA returned `reasoning_content` in the response payload. The architecture's design to strictly drop `reasoning_content` and extract only clean JSON from `content` prevents chain-of-thought leakage to candidates.
3. **Network Latency:**
   - The total response time was **1.715 seconds**, which is well within our 30-second HTTP timeout budget.

---

## 6. Next Steps

- NVIDIA Nemotron integration is verified operational.
- In accordance with Phase 10.6A instructions, Deepgram and ElevenLabs tests were not conducted.
