---
name: premium-saas-visual-patterns
description: >
  Use this skill when making visual design decisions for the Alpha Pro MENA CRM.
  It documents the brand identity, design philosophy, and premium SaaS visual patterns
  established during the visual redesign project. Activate when adding new UI components,
  pages, or modifying existing visual styles to ensure consistency with the established
  design system. Also activate when reviewing whether a UI element matches the "Deep Navy
  + Refined Gold" brand identity or violates the established premium SaaS aesthetic.
---

# Premium SaaS Visual Patterns — Alpha Pro MENA CRM

## Brand Identity Summary

**Brand Name**: Alpha Pro MENA  
**Signature Concept**: Deep Navy + Refined Gold  
**Design Character**: Institutional Arabic luxury meets modern enterprise intelligence

### Accent Colors by Theme

| Theme | Accent | Use Case |
|-------|--------|----------|
| `black_beige` | `#c9913a` — Refined Gold | Flagship dark luxury (obsidian base) |
| `alpha_pro` | `#c9913a` — Refined Gold | Corporate MENA warm daylight |
| `pro_light` | `#3b60e4` — Sophisticated Indigo | Clean enterprise cooler |
| `pro_dark` | `#38b2f8` — Sky Blue | Focused productivity dark |

**Gold rationale**: Premium MENA institutional brands (banks, government services, luxury services) use gold as authority + warmth. The chosen `hsl(38, 65%, 52%)` gold is restrained and sophisticated — not garish yellow.

---

## Core Design Principles

### 1. Flat-First Elevation

Most surfaces are defined by **border, not shadow**. Shadow is reserved for:
- `.card-interactive:hover` → `shadow-sm` (just a hint of lift)
- Dropdown menus → `shadow-lg` (floats above content)
- Modals → `shadow-xl` (highest layer)

**Never** add `box-shadow` to static cards. Static cards use `border: 1px solid var(--border-color)` only.

### 2. Deliberate Radius Hierarchy

| Element | Token | Value |
|---------|-------|-------|
| Badges, pills | `--radius-full` | 9999px |
| Buttons, inputs, small cards | `--radius-md` | 6px |
| Section-level cards | `--radius-xl` | 12px |
| Modals, drawers | `--radius-2xl` | 16px |

Do **not** use the same radius for all elements. Bubbly radius destroys the professional feel.

### 3. Typography Hierarchy

Use `font-display` (`Plus Jakarta Sans` or `Cairo` for RTL) for:
- Card numbers (KPI values)
- Modal titles
- Page headings

Use `font-sans` (`Inter` or `Cairo` for RTL) for:
- Body text
- Labels
- Table data

**KPI number sizing**:
- Primary KPI card: `font-size: var(--text-4xl)` + `tracking-tight` + `leading-tight`
- Secondary KPI card: `font-size: var(--text-2xl)` + `tracking-tight`

### 4. Status Color System

All status colors follow a consistent formula:
- **Background**: Very light tint or translucent rgba (12-16% opacity)
- **Text**: Readable semantic version (dark on light, light tint on dark)
- **Border**: Mid-point between bg and text

Use `--status-*-bg`, `--status-*-text`, `--status-*-border` tokens. **Never** hardcode status colors.

Status → CSS class mapping in `Badge.tsx`:
- NEW, UNASSIGNED → `badge-new` → indigo family
- INTERESTED, QUALIFIED → `badge-interested` → teal family
- IN_PROGRESS, CONTACTED → `badge-inprogress` → violet family
- DEMO_* → `badge-demo` → orange family
- PROPOSAL_*, NEGOTIATION → `badge-proposal` → pink family
- WON, ACTIVE, COMPLETED → `badge-won` → green family
- LOST, CANCELLED, NOT_INTERESTED → `badge-lost` → red family
- DO_NOT_CONTACT → `badge-dnc` → neutral/gray family
- NO_ANSWER, OVERDUE, RECALL_SCHEDULED → `badge-noanswer` → amber family

### 5. Icon Policy

**Use Lucide React exclusively.** Never use:
- Emoji as functional icons (🔥, 💼, 👑, ✉️, etc.)
- Other icon libraries (Font Awesome, Heroicons, etc.)
- SVG inline icons that duplicate Lucide

Emoji may only appear in:
- User-generated content (call notes, contact descriptions)
- Data from the database being displayed verbatim

### 6. Micro-Animation Rules

Apply only to interactive elements:
```css
/* Cards (interactive only) */
.card-interactive:hover { transform: translateY(-1px); box-shadow: var(--shadow-sm); }

/* Buttons */
.btn:hover { transform: translateY(-1px); }
.btn-ghost:hover { transform: none; } /* ghost buttons don't lift */

/* Table rows */
tbody tr { transition: background-color 0.1s ease; }

/* Dropdowns & modals */
/* Entrance animations only: fade + small translateY */
```

**Never** animate: badges, text labels, dividers, static content.

**Duration guide**:
- `0.1s` — table row hover background
- `0.12s–0.15s` — interactive card hover, button lift
- `0.18s` — modal entrance
- Above `0.2s` — reserved for page transitions only

### 7. KPI Dashboard Layout Pattern

The dashboard uses a two-tier hierarchy:

**Primary tier** (4 cards, `minmax(220px, 1fr)` grid):
- Bigger number (text-4xl)
- Bigger icon container (40×40px)
- More padding (space-6)
- Uses `primary={true}` prop on MetricCard

**Secondary tier** (8 cards, `minmax(170px, 1fr)` grid):
- Smaller number (text-2xl)
- Smaller icon container (32×32px)
- Less padding (space-4)
- Default MetricCard

A `.section-divider` with `.section-divider-label` separates the two tiers.

**Primary 4**: Total Calls, Demo Agreed, Opportunities+Pipeline, Overdue Tasks  
**Secondary 8**: Emails, WhatsApp, Demo Completed, Demo Cancelled, Follow-ups, Recalls, Unassigned Leads, Active Contacts

### 8. Accessibility Requirements (WCAG 2.1 AA)

- All clickable elements must have `role="button"` (if not `<button>`) + `aria-label`
- Keyboard navigable: `tabIndex={0}` + `onKeyDown` handler for Enter/Space
- Focus ring: always use `:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px }`
- Minimum contrast: 4.5:1 for normal text, 3:1 for large text
- Never remove focus outline (`outline: none`) without providing a replacement

### 9. RTL Support Rules

- Use `[dir="rtl"]` CSS selectors in tokens.css and globals.css for overrides
- Arabic fonts: `Cairo`, `Tajawal` (already configured in `--font-sans` override for RTL)
- Phone numbers, emails: always LTR (`direction: ltr`) even in RTL layout
- Dropdowns: `left: auto; right: 0` in RTL
- Sticky columns: use `right: N` instead of `left: N` in RTL
- Never use `margin-left` for directional spacing — use `gap` or logical properties

### 10. Form & Input Standards

```css
/* Height: always 40px for standard inputs */
/* Border radius: var(--radius-md) = 6px */
/* Focus ring: 3px solid var(--color-accent-light) — NOT hardcoded rgba */
/* Placeholder: var(--neutral-400) */
```

---

## Common Mistakes to Avoid

| Anti-pattern | Correct Pattern |
|-------------|-----------------|
| `backgroundColor: 'var(--brand-50)'` | `'var(--color-primary-subtle)'` |
| `backgroundColor: 'var(--brand-100)'` | `'var(--color-primary-subtle)'` |
| `color: 'var(--brand-300)'` | `'var(--color-primary)'` |
| `backgroundColor: 'var(--brand-500)'` | `'var(--color-primary)'` |
| Using emoji as icons (`🔥`, `💼`) | `<Flame size={16} />`, `<Briefcase size={16} />` |
| `box-shadow` on static cards | `border: 1px solid var(--border-color)` |
| `var(--brand-50)` for table row hover | `var(--bg-subtle)` |
| Same `--radius-md` for everything | Use proper hierarchy from the table above |
| `background: rgba(14, 135, 235, 0.15)` | `var(--color-accent-light)` |
| Hardcoded hex colors like `#0e87eb` | `var(--color-primary)` |

---

## Token Quick Reference

```css
/* Brand & Accent */
--color-primary         /* Main brand accent */
--color-primary-hover   /* Hover state */
--color-primary-subtle  /* Light tint background (replaces --brand-50, --brand-100) */
--color-accent-light    /* Focus ring / input glow */

/* Surfaces */
--bg-app                /* Page background */
--bg-surface            /* Card / panel background */
--bg-subtle             /* Subtle row hover / nested section background */

/* Elevation */
--shadow-none           /* Static cards */
--shadow-sm             /* Card hover lift */
--shadow-lg             /* Dropdowns */
--shadow-xl             /* Modals */

/* Radius */
--radius-md   /* 6px  — buttons, inputs */
--radius-xl   /* 12px — page-level cards */
--radius-2xl  /* 16px — modals */
--radius-full /* 9999px — badges, avatars */

/* Status */
--status-won-bg / --status-won-text / --status-won-border
--status-lost-bg / --status-lost-text / --status-lost-border
/* ...same pattern for: new, interested, inprogress, demo, proposal, dnc, noanswer */
```
