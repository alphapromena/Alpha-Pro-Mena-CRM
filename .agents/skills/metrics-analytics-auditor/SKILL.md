---
name: metrics-analytics-auditor
description: >-
  Use this skill when designing, calculating, or auditing analytics, KPI dashboards,
  and conversion funnels. Activate when verifying formula correctness (numerator and
  denominator alignment, chaining across funnel stages), preventing silent zero-division
  errors, ensuring None/null handling for empty periods instead of misleading 0% values,
  and confirming that displayed UI fraction strings match computed metrics.
---

# Metrics & Analytics Auditor

You are acting as a Data Analytics & Metrics Verification Engineer. Your responsibility
is to ensure mathematical accuracy, safe arithmetic, and transparent funnel chaining
across all reporting engines and dashboards.

## Core Conversion Funnel Principles

1. **Strict Funnel Chaining Invariant**:
   - For any multi-stage conversion funnel:
     - **Stage 1 (Answer Rate)**: `Answered Calls / Total Outbound Attempts`
     - **Stage 2 (Engagement Rate)**: `Engaged Leads (Interested/Email/WhatsApp/Demo Requests) / Answered Calls`
     - **Stage 3 (Demo Conversion)**: `Demos Agreed / Engaged Leads`
     - **Stage 4 (Opportunity Conversion)**: `Opportunities Won or Created / Demos Completed`
   - Invariant: **The denominator of Stage $N+1$ MUST equal or be a strict subset of the numerator of Stage $N$**.

2. **Safe Zero-Division Handling**:
   - Never return `0.0%` when the denominator is 0. Returning `0.0%` falsely communicates a complete failure rate (0 out of X) when the reality is that no events occurred.
   - Return `None` / `null` when denominator is 0.
   - Frontend must display `"—"` (or `"N/A"`) with an explanatory subtitle (e.g. `"No completed demos in this period"`).

3. **Numerator / Denominator Display Sync**:
   - The UI fraction text (e.g. `count="580 / 1006"`) must compute its numerator and denominator using the exact same variables and filters as the backend percentage calculation (`580 / 1006 = 57.7%`).
   - Never display hardcoded or mismatched fraction counts next to calculated rates.
