---
name: matt-pocock-typescript-pro
description: >-
  Use this skill when designing TypeScript interfaces, refactoring React/TS
  code, writing type-safe models, improving code architecture, enforcing strict
  types, or implementing test-driven TypeScript solutions. Contains authoritative
  guidelines and patterns inspired by Matt Pocock's Total TypeScript engineering
  standards.
---

# Matt Pocock TypeScript Professional Engineering Standard

This skill provides industry-leading TypeScript design and refactoring rules for mission-critical enterprise applications.

## Core Principles

1. **Explicit Return Types on Public APIs**:
   Always declare explicit return types on service methods, custom hooks, and shared utilities.

2. **Discriminated Unions over Optional Enums**:
   Model state variations as discriminated unions (e.g. `type State = { status: 'idle' } | { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: Error }`).

3. **Avoid `any` and Reckless Type Assertions (`as`)**:
   Use type guards (`is`), `unknown` with narrowing, and Zod/Pydantic runtime validations at system boundaries.

4. **Immutable State Updates**:
   Always use pure functions or immutable patterns when updating nested records or arrays.

5. **Self-Documenting Generic Constraints**:
   Constrain generic parameters meaningfully (e.g. `<TRecord extends { id: string }>(items: TRecord[])`).
