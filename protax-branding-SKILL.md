---
name: protax-branding
description: >
  Apply Intuit ProConnect Tax / ProTax Group branding to every artifact, visualization, document, presentation, and file Claude produces.
  Use this skill whenever the user asks Claude to create ANY visual output — React apps, HTML pages, landing pages,
  dashboards, charts, diagrams, presentations (PPTX), Word documents (DOCX), PDFs, spreadsheets, SVG graphics,
  or inline visualizations for the ProConnect Tax / ITA / ProTax Group audience.
  This is the accountant-facing brand palette — distinct from QuickBooks consumer green.
  The only exception is when the user explicitly asks for a different brand or unbranded output.
---

# Intuit ProConnect Tax / ProTax Branding Skill

Every artifact and visual output must follow the Intuit ProConnect Tax brand identity defined below. This is the **accountant and tax professional** brand — navy + teal — not the QuickBooks consumer green palette.

## Brand Identity

**Product:** ProConnect Tax Online (formerly Intuit Tax Online / ProSeries Online)
**Audience:** Tax professionals, CPAs, enrolled agents, bookkeepers
**Brand personality:** Professional, trustworthy, efficient, data-driven
**URL:** accountants.intuit.com

## Typography

**Primary typeface:** Avenir Next for Intuit

**Fallback stack (in order):** Avenir Next → Avenir → Arial → Helvetica → sans-serif

In CSS, always declare:
```css
font-family: 'Avenir Next for Intuit', 'Avenir Next', 'Avenir', Arial, Helvetica, sans-serif;
```

**Weight usage:**
- Headlines / titles: Bold (700) or Demi Bold (600)
- Subheadings: Medium (500) or Demi Bold (600)
- Body text: Regular (400)
- Captions / secondary text: Regular (400) at smaller size
- CTA button text: Medium (500) — never bold

**Sizing guidelines (web):**
- Display / hero: 48–64px
- H1: 36–40px
- H2: 28–32px
- H3: 22–24px
- Body: 16–18px
- Small / caption: 13–14px

## Color Palette

### Primary Brand Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| ProConnect Navy (Primary) | `#0C2340` | 12, 35, 64 | Primary text on light backgrounds, headings, nav bar, dark accents |
| ProConnect Teal (Bright) | `#00A3AD` | 0, 163, 173 | Interactive elements, highlights, CTAs, links |
| ProConnect Light Teal | `#D6F1F3` | 214, 241, 243 | Light backgrounds, subtle tints, cards, evidence callouts |
| ProConnect Blue | `#0077C5` | 0, 119, 197 | Secondary interactive elements, data series |
| ProConnect Light Blue | `#E8F4FD` | 232, 244, 253 | Warm backgrounds, card backgrounds, highlights |
| ProConnect Dark Blue | `#005A99` | 0, 90, 153 | Dark accent text on light backgrounds |
| ProConnect Mid Navy | `#0a3560` | 10, 53, 96 | Hero gradient mid-stop |
| ProConnect Deep Navy | `#0d4a7a` | 13, 74, 122 | Hero gradient end-stop |

### Neutral Colors

| Name | Hex | Usage |
|------|-----|-------|
| Black | `#000000` | Primary text, headings |
| Dark Gray | `#393A3D` | Secondary text |
| Medium Gray | `#6B6C72` | Tertiary text, placeholders |
| Light Gray | `#D4D5D9` | Borders, dividers |
| Off-White | `#F4F4F5` | Page backgrounds, cards |
| White | `#FFFFFF` | Backgrounds, text on dark |

### Alert & Status Colors

| Name | Hex | Usage |
|------|-----|-------|
| Alert Red | `#D93025` | Error states, urgent alerts |
| Amber | `#F59E0B` | Warnings, agent accent |
| Purple | `#7C3AED` | Consumer segment accent |

### CTA Button Colors

Primary CTA buttons use ProConnect Teal:
- **Background:** `#00A3AD`
- **Text:** `#FFFFFF` (white)
- **Font weight:** Medium (500) — never bold
- **Hover:** Darken to `#008891`
- **Border-radius:** 24px (pill shape) for primary CTAs, 8px for secondary
- **Padding:** 12px 32px
- **Text transform:** None (sentence case)

Secondary CTA buttons:
- **Background:** transparent
- **Border:** 2px solid `#00A3AD`
- **Text:** `#00A3AD`
- **Hover:** light teal fill `#D6F1F3`

Tertiary / text links:
- **Color:** `#0077C5`
- **Hover:** underline
- **Font weight:** Medium (500)

## Layout Principles

- Use an 8px spacing grid (8, 16, 24, 32, 48, 64, 96)
- Maximum content width: 1200px for web layouts
- Generous whitespace — let elements breathe
- Left-align body text (never justify)
- Cards: white background, subtle border (`#D4D5D9`) or shadow, 16px border-radius, 24–32px padding
- Professional density — slightly more information-dense than QB consumer; audience is power users

## Hero / Banner

Use a **navy gradient** for hero banners and dark sections:
```css
background: linear-gradient(135deg, #0C2340 0%, #0a3560 60%, #0d4a7a 100%);
```

Teal accent glow orb (decorative):
```css
background: rgba(0, 163, 173, 0.08);
```

## Applying Branding by Output Type

### React / HTML Artifacts
- Set CSS custom properties at `:root` for all brand colors
- Apply the font stack globally
- Use the CTA button styles defined above for all interactive buttons
- Background: white or off-white (`#F4F4F5`)
- Ensure WCAG 2.1 AA contrast on all text (navy on white passes at all sizes)

### Presentations (PPTX)
- Title slide: Navy (`#0C2340`) background, white text, ProConnect wordmark in corner
- Content slides: White background, navy headings, black body text
- Accent color: ProConnect Teal or Blue for charts and highlights
- Insert logo on every slide (bottom-right or top-left, small)

### Documents (DOCX / PDF)
- Heading color: ProConnect Navy (`#0C2340`)
- Body text: Black, 11–12pt
- Logo in header or title page
- Accent lines/dividers: Teal or Light Gray
- Page margins: 1 inch (2.54 cm)

### Charts & Visualizations
- Primary data series: ProConnect Navy (`#0C2340`)
- Secondary series: ProConnect Teal (`#00A3AD`)
- Tertiary: ProConnect Blue (`#0077C5`)
- Additional: Alert Red (`#D93025`), Amber (`#F59E0B`)
- Background: White or Off-White
- Grid lines: Light Gray (`#D4D5D9`)
- Labels: Dark Gray (`#393A3D`), use the brand font stack

### Spreadsheets (XLSX)
- Header row: ProConnect Navy background, white bold text
- Alternating rows: white and Off-White (`#F4F4F5`)
- Accent borders: Light Gray
- Number formatting: consistent decimal places, currency symbols where appropriate

## CSS Starter Template

```css
:root {
  /* ProConnect brand blues & teals */
  --pt-navy: #0C2340;
  --pt-teal: #00A3AD;
  --pt-teal-hover: #008891;
  --pt-teal-light: #D6F1F3;
  --pt-blue: #0077C5;
  --pt-blue-light: #E8F4FD;
  --pt-blue-dark: #005A99;

  /* Neutrals */
  --pt-black: #000000;
  --pt-dark-gray: #393A3D;
  --pt-medium-gray: #6B6C72;
  --pt-light-gray: #D4D5D9;
  --pt-off-white: #F4F4F5;
  --pt-white: #FFFFFF;

  /* Status */
  --pt-error: #D93025;
  --pt-amber: #F59E0B;
  --pt-purple: #7C3AED;

  /* CTA */
  --pt-cta-bg: #00A3AD;
  --pt-cta-hover: #008891;
  --pt-cta-text: #FFFFFF;

  /* Typography */
  --pt-font: 'Avenir Next for Intuit', 'Avenir Next', 'Avenir', Arial, Helvetica, sans-serif;
  --pt-line-height: 1.2;
  --pt-body-line-height: 1.5;
}

body {
  font-family: var(--pt-font);
  color: var(--pt-black);
  background: var(--pt-white);
  line-height: var(--pt-body-line-height);
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4, h5, h6 {
  color: var(--pt-navy);
  line-height: var(--pt-line-height);
  font-weight: 700;
}

.btn-primary {
  background: var(--pt-cta-bg);
  color: var(--pt-cta-text);
  border: none;
  border-radius: 24px;
  padding: 12px 32px;
  font-family: var(--pt-font);
  font-weight: 500;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-primary:hover {
  background: var(--pt-cta-hover);
}

.btn-secondary {
  background: transparent;
  color: var(--pt-cta-bg);
  border: 2px solid var(--pt-cta-bg);
  border-radius: 24px;
  padding: 12px 32px;
  font-family: var(--pt-font);
  font-weight: 500;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-secondary:hover {
  background: var(--pt-teal-light);
}
```

## Checklist (review before delivering any output)

Before delivering any artifact or visual, verify:
- [ ] Font stack is applied (Avenir Next for Intuit with fallbacks)
- [ ] Heading color is ProConnect Navy (`#0C2340`), not QB green
- [ ] CTA buttons use `#00A3AD` teal background, white text, medium weight (not bold), pill shape
- [ ] Hero/nav uses navy gradient — NOT QB spearmint green
- [ ] Evidence callouts use Light Teal `#D6F1F3` background — NOT QB olive green
- [ ] Card highlights use Light Blue `#E8F4FD` — NOT QB honey yellow
- [ ] Color contrast meets WCAG 2.1 AA (4.5:1 for text, 3:1 for large text)
- [ ] Spacing uses the 8px grid
- [ ] No QB green (`#2CA01C`, `#003E31`, `#3BD85E`) appears anywhere
