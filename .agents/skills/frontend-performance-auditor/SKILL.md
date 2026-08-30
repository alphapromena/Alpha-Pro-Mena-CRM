---
name: frontend-performance-auditor
description: >-
  Use this skill when auditing bundle size, rendering performance, network
  efficiency, route-level code splitting, API request deduplication, and
  preventing performance bottlenecks in large single-page web applications.
---

# Frontend Performance Audit Standard

## Core Performance Rules

1. **Bundle & Asset Optimization**:
   - Split routes dynamically using `React.lazy()` and `Suspense`.
   - Keep production bundle chunks under reasonable limits and avoid bundling unused icon packs.

2. **Network Deduplication**:
   - Deduplicate parallel API calls to the same endpoint.
   - Cache user profile, system settings, and team rosters across page transitions.

3. **Virtualization & DOM Pruning**:
   - For lists exceeding 100 rows, use pagination or virtual scrolling.
   - Clean up event listeners and intervals in `useEffect` cleanup return functions.
