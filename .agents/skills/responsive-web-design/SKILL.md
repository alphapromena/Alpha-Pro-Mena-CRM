---
name: responsive-web-design
description: >-
  Use this skill when implementing or reviewing responsive layouts, breakpoint
  decisions, mobile navigation, responsive tables, touch interactions, or any
  layout that must work across desktop, tablet, and mobile. The CRM is
  primarily desktop-focused but must remain functional and usable on smaller
  devices. Activate when screen-size adaptation is needed for any component or page.
---

# Responsive Web Design

You are acting as a Senior Responsive Web Design Engineer. Your responsibility
is to ensure every interface adapts correctly across all target screen sizes
with the desktop experience as the primary reference point.

## Breakpoint System

```css
/* Mobile first approach */
/* xs: < 480px  — small mobile */
/* sm: ≥ 480px  — large mobile */
/* md: ≥ 768px  — tablet */
/* lg: ≥ 1024px — laptop (primary CRM target) */
/* xl: ≥ 1280px — desktop */
/* 2xl: ≥ 1536px — large desktop */

:root {
  --breakpoint-sm:  480px;
  --breakpoint-md:  768px;
  --breakpoint-lg:  1024px;
  --breakpoint-xl:  1280px;
  --breakpoint-2xl: 1536px;
}
```

## CRM Layout Priority

The CRM is a **desktop-first** application used primarily by sales teams at
desks on laptops and monitors (1024px–1920px). Mobile is a secondary target
for quick reference, not primary workflows.

### Desktop Layout (1024px+) — Primary Target
- Fixed sidebar (240px wide) + main content area.
- Multi-column layouts: detail page sidebar + main, dashboard grid.
- Full data tables with all columns visible.
- Filter bars visible inline.

### Tablet Layout (768px–1023px) — Secondary Target
- Collapsible sidebar (icon-only or slide-over).
- Reduce columns in dashboard grid (2 → 1 column for KPI cards).
- Tables: hide less-important columns, enable horizontal scroll.
- Filter bar: collapse to a "Filters" button opening a drawer.

### Mobile Layout (< 768px) — Tertiary Target
- Sidebar: hidden, accessible via hamburger menu (slide-over).
- Single-column layout everywhere.
- Tables: card-based layout instead of traditional table OR horizontal scroll.
- Essential actions only visible; secondary actions in a "More" menu.
- Tap targets: minimum 44px × 44px.

## Navigation Responsiveness

### Desktop
- Fixed left sidebar, always visible.
- Navigation items with icon + label.

### Tablet
- Sidebar collapsed to icon-only by default.
- Hover to expand (or toggle button).

### Mobile
- Hamburger button in top bar.
- Navigation drawer slides in from left.
- Overlay backdrop when open.
- Close on navigation or backdrop tap.

## Responsive Tables

Tables are the biggest responsive challenge in CRM applications.

### Strategy: Column Priority System
Assign each column a priority:
- Priority 1: ALWAYS visible (name, status, primary action).
- Priority 2: Visible at tablet+ (email, phone, owner).
- Priority 3: Desktop only (company, country, created date).

```css
/* Hide priority-3 columns on tablet */
@media (max-width: 1023px) {
  .col-desktop-only { display: none; }
}

/* Hide priority-2 columns on mobile */
@media (max-width: 767px) {
  .col-tablet-plus { display: none; }
}
```

### Mobile Table Alternative: Card Layout
On mobile, transform table rows into cards:
```
┌──────────────────────────────┐
│ John Doe                     │
│ CONTACTED  •  Sara K. (owner)│
│ 📞 +962-77-123-4567          │
│ [Log Call]  [View]           │
└──────────────────────────────┘
```

## Responsive Typography

```css
h1 { font-size: clamp(1.5rem, 3vw, 2.25rem); }
h2 { font-size: clamp(1.25rem, 2.5vw, 1.875rem); }
body { font-size: clamp(0.875rem, 1.5vw, 1rem); }
```

## Touch Interactions

- Minimum tap target: 44px × 44px (WCAG 2.5.5).
- Spacing between tap targets: minimum 8px.
- Avoid hover-only interactions — provide tap alternatives.
- Swipe gestures (optional): swipe to reveal actions on table rows.
- No hover-dependent tooltips on mobile — use tap to show.

## Form Responsiveness

- Full-width inputs on mobile and tablet.
- Side-by-side fields (first/last name) stack vertically on mobile.
- Sticky submit button at bottom of screen on mobile forms.
- Date pickers use native mobile date input on mobile devices.

## Dashboard Responsiveness

```css
/* Desktop: 4 columns */
.kpi-grid { grid-template-columns: repeat(4, 1fr); }

/* Tablet: 2 columns */
@media (max-width: 1023px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}

/* Mobile: 1 column */
@media (max-width: 767px) {
  .kpi-grid { grid-template-columns: 1fr; }
}
```

## Modal Responsiveness

- Desktop/tablet: centered overlay, max-width defined per size.
- Mobile: bottom sheet pattern (slides up from bottom, full width, rounded top corners).

## Density Handling

- On high-DPI screens: ensure SVG icons and images are crisp.
- Provide 2x image assets where raster images are used.
- Use `min-resolution` media queries for high-DPI-specific adjustments.

## Testing Checklist

Before shipping any page:
- [ ] Tested at 375px (iPhone SE — smallest common mobile).
- [ ] Tested at 768px (iPad portrait).
- [ ] Tested at 1024px (laptop, primary target).
- [ ] Tested at 1440px (standard desktop).
- [ ] No horizontal scroll at any breakpoint (except intentional table scroll).
- [ ] Touch targets ≥ 44px on mobile.
- [ ] Navigation accessible on all sizes.
- [ ] Tables usable (horizontal scroll or card layout) on mobile.
- [ ] Text readable without zoom on mobile (minimum 16px base).

## What NOT to Do

- Do NOT hide important primary actions on mobile.
- Do NOT use fixed pixel widths that prevent shrinking.
- Do NOT rely on hover interactions alone.
- Do NOT create a separate "mobile site" — use responsive CSS.
- Do NOT ignore tablet breakpoint (768px–1023px).
- Do NOT use viewport-relative units (`vw`) for text without clamp.
