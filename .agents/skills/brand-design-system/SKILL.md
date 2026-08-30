---
name: brand-design-system
description: >-
  Use this skill when applying the Alpha Pro MENA branding kit to any UI
  component, page, or design token. Activate when a branding kit or brand
  guidelines document is provided and needs to be translated into design
  tokens, color palettes, typography choices, logo usage rules, or component
  styling. Also activate when any UI element might violate brand consistency.
  This skill holds the authoritative brand rules — they override generic design
  preferences.
---

# Brand Design System — Alpha Pro MENA

You are acting as a Brand System Architect for the Alpha Pro MENA CRM project.
Your responsibility is to faithfully translate the Alpha Pro MENA branding kit
into a precise, consistent design token system and enforce brand compliance
across every UI component.

## Brand Kit Status: EXTRACTED & APPLIED

The authentic **Alpha Pro MENA Branding Kit** has been provided and extracted:
- **Source File**: `Alpha MENA Branding Kit (1).pdf` (located at repository root)
- **Extracted Assets**: `frontend/src/components/common/BrandLogo.tsx`, `frontend/public/logo-alpha-dark.png`, `frontend/public/logo-alpha-light.png`
- **Applied Design Tokens**: `frontend/src/styles/tokens.css` (active across all 4 themes)

---

## Brand Specification (Extracted from Kit)

### 1. Authoritative Color Palette
| Color Name | Hex Code | Role in Design System |
|------------|----------|-----------------------|
| **Brand Crimson** | `#FF1E57` | Primary brand accent, primary CTA buttons, active states, left logo loop |
| **Deep Crimson-Pink** | `#E92156` | Hover state for buttons, secondary accent, active indicator |
| **Rich Berry** | `#B7274F` | Deep magenta accent, subtle borders, focused states |
| **Dark Charcoal** | `#313234` | Primary dark surface, dark mode elevated cards, right logo loop on light bg |
| **Warm Off-White** | `#F3F2F1` | Light background base, dark mode text `#F3F2F1`, right logo loop on dark bg |
| **Midnight Black** | `#000000` / `#16171A` | Pure contrast, sidebar background, deep luxury dark mode |

### 2. Typography Rules
- **English Display & Body**: **Barlow** (Google Fonts `Barlow:wght@400;500;600;700;800;900`)
- **Logo Typography**: "ALPHA PRO" in All Capital Letters, Bold (`800`), "MENA" spaced uppercase (`500/600`, letter-spacing `0.22em`)
- **Arabic Typography**: **Cairo** (`400;600;700`) / **Tajawal** for RTL localization.

### 3. Logo Mark & Variations
- **Interlocking Loop Symbol**: Left loop `#FF1E57`, Right loop `#F3F2F1` (on dark) or `#313234` (on light).
- **Variations**:
  - Dark Theme: White/Off-White text + Crimson loop
  - Light Theme: Charcoal text + Crimson loop
  - Mark-only: SVG vector or cropped high-res PNG (`BrandLogoMark.tsx`)

### 1. Color Palette
Extract and name every color in the kit:
- Primary brand color(s) and their full shade ramp (50–900 scale if not provided).
- Secondary / accent colors.
- Neutral / gray palette.
- Background colors (page, surface, card, sidebar).
- Text colors (primary, secondary, muted, inverse).
- State colors (success, warning, error, info) — align with brand if specified.
- Border colors.
- Any gradient definitions (start, end, direction, usage context).

Convert every color to both HEX and HSL. Define as CSS custom properties:
```css
:root {
  --color-brand-primary: #_____;
  --color-brand-primary-dark: #_____;
  /* etc. */
}
```

### 2. Typography
Extract:
- Primary typeface name (and Google Fonts or self-hosted source).
- Secondary / display typeface if applicable.
- Monospace typeface if specified.
- Font weight usage rules (which weights for headings, body, labels).
- Type scale (specific sizes for H1–H6, body, caption).
- Line-height values.
- Letter-spacing values if specified.
- Any rules about text transformation (uppercase for headings, etc.).

### 3. Logo Usage Rules
Extract:
- Primary logo SVG / PNG.
- Secondary/alternate logos (light/dark versions, icon-only mark).
- Minimum size requirements.
- Clear space requirements (exclusion zone around logo).
- Forbidden usages (stretching, recoloring, placing on incompatible backgrounds).
- Logo placement rules (top-left in navigation, centered in auth pages, etc.).

### 4. Spacing & Layout
Extract:
- Base spacing unit (if specified — often 4px or 8px).
- Layout grid (columns, gutters, margins).
- Any specific padding/margin rules for key components.

### 5. Border & Shape Language
Extract:
- Border radius values (sharp/angular vs. rounded — brand personality).
- Border width conventions.
- Shadow style (elevation style — subtle vs. dramatic).

### 6. Component Styling Rules
Map brand rules to specific component styles:

| Component | Brand Rule to Apply |
|-----------|---------------------|
| Primary button | Brand primary color + hover state |
| Navigation | Brand background color, active state color |
| Sidebar | Brand sidebar background (dark/light) |
| KPI cards | Border or accent color treatment |
| Data tables | Header background, row hover color |
| Status badges | Ensure brand-compatible colors |
| Charts | Brand color palette for data series |

### 7. Dashboard & Chart Styling
- Chart color series aligned with brand palette (avoid generic chart defaults).
- KPI card styling reflects brand aesthetic (border accent, icon color).
- Dashboard background treatment (pure white, subtle tint, dark).

### 8. Forbidden Patterns (to be filled from kit)
List any usage restrictions from the brand kit:
- Colors that may NOT be used.
- Combinations that are prohibited.
- Font weights that may NOT be used.
- Any other brand violations.

---

## Token Override Process

Once brand colors are extracted, update the design system token file:

```css
/* src/styles/tokens.css */
:root {
  /* Override with Alpha Pro MENA brand values */
  --color-brand-50:  /* from kit */;
  --color-brand-500: /* from kit */;
  --color-brand-600: /* from kit */;
  /* etc. */

  --font-sans: /* brand typeface */ , system-ui, sans-serif;
  /* etc. */
}
```

Propagate changes to every component that references these tokens — do NOT
update individual components separately.

---

## Brand Compliance Checklist

Before any screen or component ships, verify:
- [ ] Colors sourced exclusively from brand tokens (no arbitrary hex values).
- [ ] Typography uses brand typeface at correct weights.
- [ ] Logo rendered at correct size with required clear space.
- [ ] Button hierarchy matches brand action hierarchy.
- [ ] No gradient or visual effect not sanctioned by the brand kit.
- [ ] Charts use brand color series.
- [ ] Status badges respect brand color relationships.

---

## What NOT to Do

- Do NOT invent brand colors before the branding kit is provided.
- Do NOT use generic placeholder colors in "temporary" components — they become permanent.
- Do NOT apply the brand partially (some components branded, others not).
- Do NOT override brand tokens locally in individual components.
- Do NOT stretch, recolor, or modify the logo.
- Do NOT use font weights outside those specified in the brand kit.
