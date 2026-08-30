---
name: react-typescript-expert
description: >-
  Use this skill when building, refactoring, or optimizing React components with
  strict TypeScript typing. Enforces optimal hook architecture, memoization,
  reusable compound components, strict prop contracts, and avoidance of
  unnecessary re-renders in data-intensive applications.
---

# React TypeScript Enterprise Engineering Standard

## Guidelines

1. **Strict Props & Data Contracts**:
   - Every component must define an explicit `interface ComponentProps`.
   - Use union types for status and variant flags (`'primary' | 'secondary' | 'ghost'`).

2. **Hook Optimization & Stable Handlers**:
   - Wrap expensive computation in `useMemo`.
   - Wrap callback props passed to children in `useCallback` when children are memoized.
   - Avoid creating new object/array literals inside JSX render trees if passed down to pure components.

3. **Compound Components for Complex UI**:
   - Structure complex UI (Modals, Tables, Dropdowns) into cohesive subcomponents with shared context.
