---
name: interaction-design-engineer
description: >-
  Use this skill when designing, polishing, or reviewing UI interactions, hover
  states, active focus rings, button clicks, modal transitions, toast
  notifications, and keyboard shortcuts. Enforces responsive, snappy 120-220ms
  micro-interactions that feel premium and tactile.
---

# Interaction Design Engineering Standard

## Interaction Rules

1. **Restrained Micro-Transitions**:
   - Transition duration: `120ms` to `200ms` with `cubic-bezier(0.4, 0, 0.2, 1)`.
   - Never use slow, exaggerated bouncy animations that delay power users.

2. **Visual Feedback States**:
   - Buttons: Hover subtle brightness lift, Active `:active` slight scale down (`scale(0.98)`).
   - Rows: Subtle background highlight on hover (`var(--bg-subtle)`).
   - Inputs: Visible crisp focus ring using `--color-accent` or `--color-primary`.

3. **Accessible Keyboard Navigation**:
   - Modal dialogs must trap focus and close on `Escape`.
   - Tables and dropdowns must allow keyboard item selection.
