# HTML Design Quality Standard

> Source: Adapted from ECC frontend-slides discipline — patterns only, not the full system.
> Purpose: Ensure every DeepSite AI-generated HTML page reaches Awwwards/Dribbble quality.

---

## Non-Negotiables

Every generated page MUST satisfy ALL of the following:

1. **Distinctive visual identity** — Do NOT produce a generic purple-to-blue gradient over white text. Every page must have a unique aesthetic anchored to the user's content type.
2. **Atmospheric backgrounds** — Use layered CSS gradients, subtle noise texture (SVG `feTurbulence` or a CSS pattern), or geometric SVG shapes. A flat solid color or a simple two-stop gradient alone is insufficient.
3. **Strong type hierarchy** — Minimum 3 distinct font-size levels (display / body / caption). Every font size MUST use `clamp()` for fluid, breakpoint-free responsiveness. Example: `font-size: clamp(2.5rem, 6vw, 5rem)`.
4. **CSS custom properties** — All theme values (colors, spacing, font sizes, radius, shadows) defined in `:root {}`. No hardcoded hex values repeated in the stylesheet.
5. **Meaningful animations** — At least one scroll-triggered reveal using Intersection Observer. Hover micro-interactions on every interactive element (button, card, link, icon). Transitions must feel intentional, not defaulted to `all 0.3s`.
6. **Accessibility baseline** — `@media (prefers-reduced-motion: reduce)` present and disabling animations. Sufficient color contrast. Semantic HTML elements used correctly.
7. **Real images** — Unsplash CDN URLs only (`https://images.unsplash.com/photo-{ID}?w={W}&h={H}&fit=crop&auto=format`). Never placeholders, local paths, or broken `src` attributes.

---

## Anti-Patterns (NEVER produce)

These patterns result in immediate quality failure:

- **The startup template** — white or #1a1a1a background, Inter or system font, purple-to-blue gradient hero, three feature cards, generic CTA button. This is the most common failure.
- **Flat dark background with nothing else** — `background: #0f0f0f` alone with no texture, no depth, no atmospheric layer.
- **Generic gradient only** — Two-stop gradient with no additional visual elements (noise, shapes, overlays, patterns).
- **System font stack without a web font** — `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI'...` with no actual Google Font or @font-face loaded. Every design must load at least one intentional web font.
- **Static page** — Every section needs at least one animation or interactive element. A page where nothing moves or responds is unacceptable.
- **Monotone palette** — Single-hue palette with no accent, contrast color, or highlight. Every design needs a tension between at least 2 distinct hue families.
- **Hardcoded pixel font sizes** — `font-size: 14px`, `font-size: 24px` scattered throughout the CSS. Use `clamp()` and CSS custom properties instead.
- **Inline style color values** — `style="color: #333"` in HTML markup. All visual decisions belong in CSS.
- **Lorem ipsum text** — Never use placeholder text. Use realistic dummy content that matches the page's purpose.
- **Excessive box shadows on everything** — One or two intentional shadows per design. Not `box-shadow: 0 4px 20px rgba(0,0,0,0.1)` on every div.

---

## Visual Quality Checklist

Run this checklist before finalizing the output. All 6 must pass for APPROVED status:

- [ ] **Atmospheric hero** — Full-viewport hero section with layered gradient, texture, or pattern background (not a single flat color).
- [ ] **Section separation** — Minimum 3 visually distinct sections. Each section has its own background treatment or clear visual boundary.
- [ ] **Hover states** — Every `<button>`, `<a>`, and card element has a `:hover` style that is visually distinct and uses `transition`.
- [ ] **`clamp()` usage** — All font-size and major spacing values use `clamp()`. No bare `px` font sizes.
- [ ] **`prefers-reduced-motion`** — `@media (prefers-reduced-motion: reduce)` block is present and sets `animation: none` / `transition: none`.
- [ ] **No plain-template risk** — Page does not look like a generic SaaS landing page or a Bootstrap/Tailwind starter template. It has a unique visual character.

**Scoring:**
- 6/6 → APPROVED
- 5/6 → APPROVED (note which criterion was skipped and why)
- 4/6 or fewer → NEEDS_REVISION — list failing criteria explicitly

---

## CSS Techniques Reference

Preferred techniques for achieving quality output:

```css
/* Atmospheric background with noise */
body {
  background:
    radial-gradient(ellipse at 20% 50%, hsla(220, 80%, 15%, 0.8) 0%, transparent 60%),
    radial-gradient(ellipse at 80% 20%, hsla(280, 70%, 10%, 0.6) 0%, transparent 50%),
    url("data:image/svg+xml,...") /* SVG noise */,
    hsl(230, 25%, 6%);
}

/* CSS custom properties in :root */
:root {
  --color-bg: hsl(230, 25%, 6%);
  --color-surface: hsl(230, 20%, 10%);
  --color-accent: hsl(155, 80%, 55%);
  --color-text: hsl(220, 20%, 90%);
  --color-muted: hsl(220, 15%, 55%);
  --font-display: clamp(3rem, 8vw, 7rem);
  --font-heading: clamp(1.75rem, 4vw, 3rem);
  --font-body: clamp(1rem, 2vw, 1.125rem);
  --space-section: clamp(4rem, 10vw, 8rem);
  --radius: 0.75rem;
}

/* Intersection Observer reveal */
.reveal {
  opacity: 0;
  transform: translateY(2rem);
  transition: opacity 0.6s ease, transform 0.6s ease;
}
.reveal.visible {
  opacity: 1;
  transform: none;
}
@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1; transform: none; transition: none; }
}

/* Strong type hierarchy */
.display { font-size: var(--font-display); font-weight: 800; line-height: 1.05; }
.heading  { font-size: var(--font-heading); font-weight: 700; line-height: 1.2; }
.body-lg  { font-size: var(--font-body);   font-weight: 400; line-height: 1.7; }
```
