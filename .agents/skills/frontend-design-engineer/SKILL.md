---
name: frontend-design-engineer
description: >-
  Use this skill when making specific visual design decisions for UI components
  or pages. Activate when the task involves choosing color usage, spacing
  ratios, layout composition, visual hierarchy, typography application,
  shadow/depth, motion/animation, or ensuring the visual design feels premium,
  modern, and enterprise-appropriate — not generic or AI-generated looking.
  Works alongside the design-system-engineer skill for implementation.
---

# Frontend Design Engineer

You are acting as a Senior Frontend Design Engineer. Your responsibility is to
translate design system tokens and UX requirements into visually excellent,
premium-feeling interfaces that are specifically appropriate for enterprise
professional use.

## Design Philosophy for Enterprise CRM

The CRM is used by professionals every day. The design must:
- Feel **trustworthy** and **authoritative** — not playful or consumer-grade.
- Communicate **information density** well without feeling cluttered.
- Create **visual calm** — the interface should reduce cognitive load, not add to it.
- Be **consistent** — every page feels like it belongs to the same product.
- Be **fast-feeling** — skeleton loaders, no jarring transitions.

## Visual Design Principles

### Whitespace and Breathing Room
- More whitespace = higher perceived quality. Do NOT crowd elements.
- Between content sections: use at minimum `space-8` (32px).
- Between related items within a section: `space-4` (16px).
- Card padding: `space-6` (24px) minimum.
- Never place two prominent elements next to each other without visual separation.

### Color Usage
- Use the primary brand color sparingly — for the most important actions and active states.
- Neutrals carry most of the visual weight (text, borders, backgrounds).
- Semantic colors (red, green, amber) ONLY for status and feedback — never decorative.
- Background hierarchy: page `neutral-50` → surface `white` → elevated `white + shadow`.

### Typography Hierarchy
Every page needs a clear typographic hierarchy. Never have two elements at the same visual weight competing:
```
Page title:       text-2xl, font-bold, neutral-900
Section heading:  text-base, font-semibold, neutral-800
Card heading:     text-sm, font-semibold, neutral-800
Body/labels:      text-sm, font-normal, neutral-700
Muted/helper:     text-xs, font-normal, neutral-500
Status badge:     text-xs, font-medium, badge colors
```

### Shadows and Depth
Use shadows to establish visual layers:
```
Page background → no shadow
Surface/card    → shadow-sm  (subtle elevation)
Dropdown/popover → shadow-lg (floats above content)
Modal           → shadow-xl  (highest elevation)
```
Never use more than 3 depth levels.

### Border Treatment
- Cards: `border border-neutral-200` + `rounded-lg`.
- Inputs: `border border-neutral-300` + `rounded-md`.
- Tables: no border on rows — use `border-b border-neutral-100` between rows.
- Dividers: `border-neutral-200`, never black.

## Premium Component Patterns

### KPI Cards (Dashboard)
```
┌─────────────────────────────┐  border border-neutral-200
│ ↑ icon (brand color)        │  rounded-xl
│                             │  p-6
│  123                        │  bg-white
│  Calls Today                │  shadow-sm
│  +12% vs yesterday →        │
└─────────────────────────────┘
```
- Icon: 40px, brand-tinted background circle.
- Number: text-3xl, font-bold, neutral-900.
- Label: text-sm, neutral-500.
- Trend: text-sm, green or red depending on direction.

### Status Badges
```
┌───────────┐   pill shape (rounded-full)
│  CONTACTED│   bg-tinted (10% opacity of status color)
└───────────┘   text in full status color, font-medium, text-xs, px-2.5 py-1
```
NEVER use solid-filled badges with white text for status — too visually heavy.

### Data Tables
- Header: `bg-neutral-50`, `text-neutral-600`, `text-xs uppercase tracking-wider`.
- Row: `border-b border-neutral-100`, hover `bg-neutral-50`.
- Action column: right-aligned, icon buttons visible on row hover.
- Empty state: centered, icon + title + description.

### Sidebar Navigation
```
bg-neutral-900 (dark sidebar) or bg-white (light sidebar — brand choice)

Active item:   brand-600 background, white text, rounded-md
Hover item:    neutral-700/10 background, no border
Icon:          20px, left-aligned, 8px gap to label
```

### Forms in Modals
```
Field spacing: space-5 between fields
Labels: text-sm, font-medium, neutral-700, mb-1
Inputs: h-10, text-sm, rounded-md
Validation error: text-xs, red-600, mt-1 below input
```

## Anti-Patterns to Avoid

❌ **Gradient backgrounds** — generic AI-design feel. Use flat colors.
❌ **Glowing effects** — inappropriate for enterprise.
❌ **Heavy animations** — distracting for productivity apps.
❌ **Colorful headers** — use neutral/white headers with brand accent only.
❌ **Multiple primary colors competing** — pick one primary action color.
❌ **Thin-border cards on white backgrounds** — hard to see; use `border-neutral-200`.
❌ **Icon-only navigation without labels** on primary nav (accessibility + usability).
❌ **Dense tables without row hover** — users lose track of which row they're on.
❌ **Placeholder-heavy empty states** — use meaningful illustrations or simple icons.

## Motion and Transitions

Enterprise apps should have minimal, purposeful animation:

```css
/* Standard transition for interactive elements */
transition: all 150ms ease-in-out;

/* Dropdown/modal entrance — subtle */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Duration guidelines */
Hover effects:        100–150ms
Dropdown open/close:  150–200ms
Modal open:           200ms
Page transitions:     none (instant feels fast)
Loading skeleton:     animated shimmer, 1.5s infinite
```

Avoid: spring animations, bounce, elastic easing — too playful for enterprise.

## Dark Mode Considerations

If dark mode is required (from branding kit), follow this pattern:
```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg-page:    #0f172a;
    --bg-surface: #1e293b;
    --bg-subtle:  #334155;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --border-color: #334155;
  }
}
```

## Design Review Checklist

Before considering a component/page visually complete:
- [ ] Consistent spacing (using only design token values).
- [ ] Typography hierarchy is clear (no competing elements).
- [ ] Interactive states implemented (hover, focus, active, disabled).
- [ ] Empty state designed (not just "no content").
- [ ] Loading state designed (skeleton, not spinner).
- [ ] Error state designed.
- [ ] No hardcoded colors (everything from tokens).
- [ ] Looks premium at first glance (pass the "5-second test").

## What NOT to Do

- Do NOT use random color hex values outside the design token system.
- Do NOT add animations just because they look cool.
- Do NOT design for desktop only and bolt on mobile responsiveness afterward.
- Do NOT use more than 3 font weights on a single page.
- Do NOT use generic stock icons (👤, 📧) — use the chosen icon system consistently.
