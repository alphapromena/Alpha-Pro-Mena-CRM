---
name: visual-consistency-auditor
description: >-
  Use this skill when performing design audits to identify and eliminate
  inconsistent spacing, unaligned borders, random hex colors, divergent border
  radii, mismatched typography, or ad-hoc styling overrides that drift from the
  design token system.
---

# Visual Consistency Audit Standard

## Audit Checklist

1. **Design Tokens Exclusivity**:
   - Zero hardcoded random hex codes (`#123456`) in component JSX. All colors must resolve through CSS variables (`var(--bg-surface)`, `var(--border-color)`, `var(--neutral-900)`).

2. **Spacing Grid Compliance**:
   - Use strict 4px/8px scale (`--space-1` = 4px, `--space-2` = 8px, `--space-3` = 12px, `--space-4` = 16px, `--space-6` = 24px).
   - Eliminate arbitrary values like 17px, 23px, 13px.

3. **Unified Component Variants**:
   - Standardize buttons across all pages into defined variants: `primary`, `secondary`, `outline`, `ghost`, `danger`.
   - Standardize table headers, search input fields, modals, and badge pills.
