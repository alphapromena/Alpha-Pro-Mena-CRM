---
name: design-system-engineer
description: >-
  Use this skill when establishing, implementing, or enforcing a design system
  or component library. Activate when the task involves design tokens,
  typography scales, spacing systems, color palettes, component variants,
  button hierarchy, input styling, table styling, card design, modal design,
  alert components, navigation components, icon systems, or ensuring visual
  consistency across the entire application.
---

# Design System Engineer

You are acting as a Senior Design System Engineer. Your responsibility is to
establish and enforce a comprehensive, consistent design system that ensures
visual coherence across every component and page.

## Design Token Foundation

All visual decisions must be expressed as design tokens. No hardcoded values.

### Color Tokens
```css
:root {
  /* Brand (will be updated from Alpha Pro MENA branding kit) */
  --color-brand-50:  #eff6ff;
  --color-brand-100: #dbeafe;
  --color-brand-500: #3b82f6;
  --color-brand-600: #2563eb;
  --color-brand-700: #1d4ed8;
  --color-brand-900: #1e3a8a;

  /* Neutrals */
  --color-neutral-0:   #ffffff;
  --color-neutral-50:  #f8fafc;
  --color-neutral-100: #f1f5f9;
  --color-neutral-200: #e2e8f0;
  --color-neutral-300: #cbd5e1;
  --color-neutral-400: #94a3b8;
  --color-neutral-500: #64748b;
  --color-neutral-600: #475569;
  --color-neutral-700: #334155;
  --color-neutral-800: #1e293b;
  --color-neutral-900: #0f172a;

  /* Semantic */
  --color-success:  #16a34a;
  --color-warning:  #d97706;
  --color-danger:   #dc2626;
  --color-info:     #0284c7;

  /* Status (CRM-specific) */
  --status-new:      #3b82f6;
  --status-progress: #6366f1;
  --status-won:      #16a34a;
  --status-lost:     #dc2626;
  --status-dnc:      #1f2937;
  --status-no-answer:#d97706;
  --status-duplicate:#94a3b8;

  /* Background */
  --bg-page:       var(--color-neutral-50);
  --bg-surface:    var(--color-neutral-0);
  --bg-subtle:     var(--color-neutral-100);
  --bg-overlay:    rgba(15, 23, 42, 0.5);
}
```

### Typography Tokens
```css
:root {
  /* Scale — Major Third (1.25×) */
  --text-xs:   0.75rem;    /* 12px */
  --text-sm:   0.875rem;   /* 14px */
  --text-base: 1rem;       /* 16px */
  --text-lg:   1.125rem;   /* 18px */
  --text-xl:   1.25rem;    /* 20px */
  --text-2xl:  1.5rem;     /* 24px */
  --text-3xl:  1.875rem;   /* 30px */
  --text-4xl:  2.25rem;    /* 36px */

  /* Weight */
  --font-normal:   400;
  --font-medium:   500;
  --font-semibold: 600;
  --font-bold:     700;

  /* Line height */
  --leading-tight:  1.25;
  --leading-normal: 1.5;
  --leading-relaxed:1.625;

  /* Font families */
  --font-sans: 'Inter', 'Segoe UI', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}
```

### Spacing Tokens
```css
:root {
  /* 4px base grid */
  --space-1:  0.25rem;  /* 4px */
  --space-2:  0.5rem;   /* 8px */
  --space-3:  0.75rem;  /* 12px */
  --space-4:  1rem;     /* 16px */
  --space-5:  1.25rem;  /* 20px */
  --space-6:  1.5rem;   /* 24px */
  --space-8:  2rem;     /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
}
```

### Border Radius Tokens
```css
:root {
  --radius-sm:   0.25rem;   /* 4px — inputs, badges */
  --radius-md:   0.5rem;    /* 8px — cards, buttons */
  --radius-lg:   0.75rem;   /* 12px — modals, panels */
  --radius-xl:   1rem;      /* 16px — large panels */
  --radius-full: 9999px;    /* pills */
}
```

### Shadow Tokens
```css
:root {
  --shadow-sm:  0 1px 2px 0 rgba(0,0,0,0.05);
  --shadow-md:  0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
  --shadow-lg:  0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.05);
  --shadow-xl:  0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04);
}
```

## Component Specifications

### Button Component
Variants × Sizes = complete button system:

| Variant | Background | Text | Border | Use Case |
|---------|-----------|------|--------|----------|
| primary | brand-600 | white | none | Primary CTA |
| secondary | transparent | brand-600 | brand-200 | Secondary action |
| ghost | transparent | neutral-600 | none | Tertiary action |
| danger | danger | white | none | Destructive action |

Sizes: `sm` (h-8, px-3, text-sm), `md` (h-10, px-4, text-base), `lg` (h-12, px-6, text-lg).
States: default, hover, focus (visible ring), active, disabled (50% opacity, no-pointer), loading (spinner inline).

### Input Component
- Height: 40px (10 × 4px grid).
- Border: 1px solid neutral-300.
- Border-radius: radius-md.
- Focus: 2px ring brand-500, border brand-500.
- Error: border danger, error message below in danger color.
- Label: always above input, font-medium text-sm.
- Placeholder: neutral-400, never used as the only label.

### Badge Component
- Used for status labels, tags, roles.
- Sizes: sm (text-xs, px-2, py-0.5), md (text-sm, px-3, py-1).
- Shape: radius-full (pill).
- Each status has a dedicated token pair (background + text).

### Table Component
- Header: bg-neutral-50, text-neutral-600, font-semibold, text-sm, border-bottom.
- Row: bg-white, hover bg-neutral-50, border-bottom neutral-100.
- Cell padding: py-3 px-4.
- Selected row: bg-brand-50.
- Sticky header: position sticky, z-index 10.
- Dense mode available for power users.

### Card Component
- Background: bg-surface.
- Border: 1px solid neutral-200.
- Border-radius: radius-lg.
- Shadow: shadow-sm.
- Padding: space-6.

### Modal Component
- Backdrop: bg-overlay.
- Container: bg-surface, radius-xl, shadow-xl.
- Header: border-bottom, py-4 px-6.
- Body: p-6.
- Footer: border-top, py-4 px-6, flex justify-end gap-3.
- Sizes: sm (max-w-sm), md (max-w-lg), lg (max-w-2xl), full (max-w-5xl).

### Alert Component
```
[icon] Title
       Description text
```
Variants: info (blue), success (green), warning (amber), error (red).
Each variant: light tinted background, border-left 4px, icon + title + optional description.

## Typography Usage Rules

- Page title: text-2xl, font-bold, neutral-900.
- Section heading: text-lg, font-semibold, neutral-800.
- Card heading: text-base, font-semibold, neutral-800.
- Body text: text-sm or text-base, font-normal, neutral-700.
- Caption / helper: text-xs, neutral-500.
- Error text: text-sm, danger color.
- Code: font-mono, text-sm, bg-neutral-100.

## Icon System

- Use a single icon library consistently (Lucide React or Heroicons).
- Icon size standards: 16px (inline), 20px (button icons), 24px (navigation).
- Always pair icons with text labels for primary actions (accessibility).
- Icon-only buttons must have `aria-label` and tooltip.

## Component Checklist (Before Shipping)

For every new component:
- [ ] Uses design tokens (no hardcoded hex/px values).
- [ ] All interactive states implemented (hover, focus, disabled, loading).
- [ ] Focus ring visible (2px, brand color).
- [ ] Keyboard navigable.
- [ ] ARIA attributes present where needed.
- [ ] Responsive (works on mobile if relevant).
- [ ] Dark mode compatible (if dark mode is required).
- [ ] Documented: props, variants, usage examples.

## What NOT to Do

- Do NOT use hardcoded color hex values outside the token file.
- Do NOT create a one-off component when a variant of an existing one would do.
- Do NOT use different shadow values than the token set.
- Do NOT break the spacing grid (use only token spacing values).
- Do NOT create custom badge colors outside the defined palette.
