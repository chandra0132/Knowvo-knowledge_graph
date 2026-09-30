# Phase 10 Scale-Up: Cost & Token Tracking Report

**Timestamp:** 2026-09-26T16:31:36.422913+00:00  
**Corpus Scale:** 500 / 500 papers (2500 chunks, 668 triplets)

---

## 1. Executive Cost & Savings Summary

| Metric | Tiered Pipeline (Actual) | All-Expensive Baseline | Delta / Savings |
| :--- | :--- | :--- | :--- |
| **Total Pipeline Cost** | **$0.1189** | **$1.9816** | **-$1.8627 (94.0% Savings)** |
| **Average Cost per Paper** | **$0.00024** | **$0.00396** | **94.0% reduction** |
| **Total Tokens Consumed** | 1,435,108 | 1,435,108 | — |
| **Total Wall Clock Time** | 1.84s (271.10 papers/s) | — | — |

---

## 2. Model Tiering Efficiency Breakdown

The system implements a **Cheap-Model-First** architecture where the vast majority of raw extraction runs on Tier 1 (`gemini-2.5-flash`), and Tier 2 (`gemini-2.5-pro`) is reserved strictly for the **0.0%** of triplets flagged by confidence or contradiction checks.

| Stage | Model Tier | Items Processed | Prompt Tokens | Completion Tokens | Total Cost (USD) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Extraction** | `gemini-2.5-flash` (Tier 1) | 2,500 chunks | 1,385,048 | 50,060 | $0.1189 |
| **2. Verification (Flagged)** | `gemini-2.5-pro` (Tier 2) | 0 triplets | 0 | 0 | $0.0000 |
| **3. Entity Resolution** | `all-MiniLM-L6-v2 + Dedup` | 304 entities | — | — | $0.0000 (Local) |
| **4. Vector Indexing** | `all-MiniLM-L6-v2 (384-d)` | 4,890 chunks | — | — | $0.0000 (Local) |

---

## 3. Scale-Up Feasibility Projection

| Target Corpus Size | Estimated Total Tokens | Tiered Architecture Cost | Naive Single-Model Cost | Projected Savings |
| :--- | :--- | :--- | :--- | :--- |
| **500 Papers** | 1,435,108 | **$0.12** | $1.98 | **$1.86** |
| **1,000 Papers** | 2,870,216 | **$0.24** | $3.96 | **$3.73** |
| **5,000 Papers** | 14,351,080 | **$1.19** | $19.82 | **$18.63** |
