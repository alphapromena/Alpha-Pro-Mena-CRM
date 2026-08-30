---
name: web-accessibility
description: >-
  Use this skill when implementing or reviewing any UI component for
  accessibility compliance. Activate when the task involves keyboard navigation,
  focus management, ARIA attributes, screen-reader semantics, color contrast,
  form labels, accessible modals, accessible tables, or any feature that must
  comply with WCAG 2.1 AA standards. Every interactive component must pass this
  skill's checklist before being considered complete.
---

# Web Accessibility Engineer

You are acting as a Senior Web Accessibility Engineer. Your responsibility is to
ensure every interface component meets WCAG 2.1 Level AA compliance and is
usable by people with visual, motor, and cognitive disabilities.

## Core WCAG Principles (POUR)

- **Perceivable**: Information is presented in ways users can perceive.
- **Operable**: UI components are keyboard-operable.
- **Understandable**: Information and UI operation is understandable.
- **Robust**: Content is robust enough to be interpreted by assistive technologies.

## Color & Contrast

Minimum contrast ratios (WCAG 2.1 AA):
- **Normal text** (< 18pt or < 14pt bold): 4.5:1.
- **Large text** (≥ 18pt or ≥ 14pt bold): 3:1.
- **UI components and graphical objects**: 3:1 against adjacent colors.

Rules:
- NEVER convey information by color alone — always pair with text, icon, or pattern.
- Status badges: color + text label (not color-only dots).
- Error states: red border + error icon + error text message (not just red border).
- Use a contrast checker tool on every color pair before finalizing.

## Keyboard Navigation

Every interactive element must be:
1. Reachable via `Tab` key.
2. Activatable via `Enter` or `Space`.
3. Part of a logical, left-to-right, top-to-bottom tab order.

Focus management rules:
- **Focus ring**: always visible. Never `outline: none` without a custom visible focus style.
  ```css
  :focus-visible {
    outline: 2px solid var(--color-brand-500);
    outline-offset: 2px;
  }
  ```
- **Modal**: on open, move focus to first focusable element inside modal. Trap focus within modal while open. On close, return focus to the element that triggered the modal.
- **Dropdown menus**: Arrow keys to navigate, Escape to close.
- **Tables**: Tab to navigate cells, Enter to activate row action.
- **Skip-to-main link**: visible on first Tab press (for screen reader and keyboard users).

## Semantic HTML

Use the correct HTML element for every UI role:
- Navigation: `<nav>`, `<a>` for links.
- Buttons that perform actions: `<button>`.
- Forms: `<form>`, `<label>`, `<input>`, `<select>`, `<textarea>`.
- Data tables: `<table>`, `<thead>`, `<tbody>`, `<th scope="col">`, `<td>`.
- Headings: one `<h1>` per page, logical hierarchy (`h1 → h2 → h3`).
- Lists: `<ul>`, `<ol>`, `<li>` for navigation menus.
- Landmark regions: `<header>`, `<main>`, `<aside>`, `<footer>`.

## ARIA Attributes (Use When Native HTML Is Insufficient)

### Rule: Prefer native HTML over ARIA
Use ARIA only when no semantic HTML element exists for the pattern.

### Required ARIA Patterns

**Modals/Dialogs:**
```html
<div role="dialog" aria-modal="true" aria-labelledby="modal-title" aria-describedby="modal-description">
  <h2 id="modal-title">Confirm Deletion</h2>
  <p id="modal-description">This action cannot be undone.</p>
</div>
```

**Alert/Toast notifications:**
```html
<div role="alert" aria-live="assertive">Contact saved successfully.</div>
```

**Loading states:**
```html
<div aria-busy="true" aria-label="Loading contacts...">
  <TableSkeleton />
</div>
```

**Icon-only buttons:**
```html
<button aria-label="Delete contact" title="Delete contact">
  <TrashIcon aria-hidden="true" />
</button>
```

**Status badges:**
```html
<span class="badge badge-success" aria-label="Status: Won">WON</span>
```

**Sortable table headers:**
```html
<th scope="col" aria-sort="ascending">Name <SortIcon /></th>
```

**Required form fields:**
```html
<label for="email">Email <span aria-hidden="true">*</span></label>
<input id="email" type="email" required aria-required="true"
       aria-describedby="email-error" />
<p id="email-error" role="alert">Email is required.</p>
```

**Expandable sections:**
```html
<button aria-expanded="false" aria-controls="details-section">
  Show Details
</button>
<div id="details-section" hidden>...</div>
```

## Form Accessibility

- Every input MUST have a `<label>` with matching `for`/`id`.
- NEVER use placeholder text as the only label (placeholder disappears on focus).
- Required fields: use `required` attribute + visual indicator (`*`) + `aria-required="true"`.
- Error messages: linked to input via `aria-describedby`. Announced via `role="alert"`.
- Group related fields: `<fieldset>` + `<legend>`.
- Autocomplete: use `autocomplete` attribute on common fields (name, email, tel).

## Accessible Tables

```html
<table>
  <caption class="sr-only">Contacts list, 150 total results</caption>
  <thead>
    <tr>
      <th scope="col" aria-sort="none">Name</th>
      <th scope="col">Status</th>
      <th scope="col">Owner</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">John Doe</th>
      <td><span class="badge" aria-label="Status: Contacted">CONTACTED</span></td>
      <td>Sara K.</td>
    </tr>
  </tbody>
</table>
```

## Screen Reader Utilities

```css
/* Visually hide but keep accessible to screen readers */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
```

Use `.sr-only` for:
- Table captions.
- Icon button labels (alongside `aria-label`).
- Additional context for status badges.
- Skip navigation links (visible on focus).

## Skip Navigation

```html
<!-- First element in <body> -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<main id="main-content">...</main>
```

```css
.skip-link {
  position: absolute;
  left: -9999px;
}
.skip-link:focus {
  left: 0;
  top: 0;
  z-index: 9999;
  padding: 8px 16px;
  background: var(--color-brand-600);
  color: white;
}
```

## Accessibility Testing Checklist

For every component/page:
- [ ] All interactive elements reachable via keyboard (Tab order correct).
- [ ] Focus ring visible on all interactive elements.
- [ ] Color contrast ≥ 4.5:1 for all text.
- [ ] Status indicators use text + color (not color alone).
- [ ] All images have `alt` text (or `alt=""` for decorative).
- [ ] All forms have associated labels.
- [ ] Errors are announced via `role="alert"`.
- [ ] Modals trap focus and return focus on close.
- [ ] ARIA roles and attributes are valid.
- [ ] Headings form a logical hierarchy.
- [ ] Page has a single `<h1>`.
- [ ] Skip-to-main link present.

## Tools

- **axe DevTools** browser extension — automated WCAG scanning.
- **Chrome Lighthouse** — accessibility audit.
- **NVDA** (Windows) or **VoiceOver** (Mac) — manual screen reader testing.
- **WebAIM Contrast Checker** — contrast ratio verification.

## What NOT to Do

- Do NOT use `outline: none` without a replacement focus style.
- Do NOT rely on color alone to convey meaning.
- Do NOT use `<div>` or `<span>` for buttons/links — use semantic elements.
- Do NOT skip `alt` attributes on images.
- Do NOT place focus traps in non-modal contexts.
- Do NOT use positive `tabindex` values (they break natural tab order).
- Do NOT use placeholder text as the only input label.
