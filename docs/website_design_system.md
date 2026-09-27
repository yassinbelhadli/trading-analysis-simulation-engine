# Website Design System

## Status

- Phase: 2.1 Website
- Status: Approved specification; W1 token layer implemented
- Source baseline: current product tokens in `admin_dashboard/app/globals.css` and `ThemeProvider`
- Approval required: logo asset, final font licensing, final copy, and final domain branding
- This system applies to the public Website only. It does not replace the frozen Client/Admin portal theme.

## Design Direction

### Brand Identity

- Product name: `ICT Funded EA Pro`
- Short label: `ICT EA Pro`
- Positioning: disciplined automation infrastructure for funded-account traders
- Promise: clarity, control, capital protection, and operational visibility
- Personality: precise, calm, technical, confident, transparent
- Avoid: guaranteed-profit language, urgency manipulation, casino imagery, fake performance claims, and unexplained trading jargon

### Visual Language

- Dark-first, instrument-panel inspired foundation
- Deep navy surfaces with blue action accents
- Technical data details used sparingly for credibility, not decoration
- Clear editorial sections for marketing content
- Strong hierarchy and generous whitespace
- Small number of meaningful visual motifs instead of generic gradients everywhere
- No emoji as primary UI icons

### Logo

Required variants:

- horizontal wordmark for desktop navigation
- compact mark for mobile and favicon
- dark-surface variant
- light-surface variant
- monochrome fallback

Logo rules:

- The wordmark must read `ICT Funded EA Pro` or the approved brand name.
- Do not recreate the logo with plain text once an approved asset exists.
- Maintain clear space equal to the height of the compact mark.
- Do not stretch, rotate, recolor outside approved variants, or place on low-contrast backgrounds.
- Final SVG/PNG assets require brand approval before implementation.

## Color Tokens

These are proposed Website tokens based on the existing product accent and dark theme. Final brand approval may change values before implementation.

### Core Palette

| Token | Value | Use |
|---|---|---|
| `--website-ink` | `#08111F` | Deepest page/background surface |
| `--website-navy` | `#0F172A` | Primary dark surface; current product baseline |
| `--website-slate` | `#1E293B` | Card and secondary surface; current product baseline |
| `--website-slate-soft` | `#334155` | Borders and muted surface |
| `--website-white` | `#F8FAFC` | Primary light text |
| `--website-muted` | `#94A3B8` | Secondary text; current product baseline |
| `--website-blue` | `#3B82F6` | Primary action; current product accent |
| `--website-blue-hover` | `#2563EB` | Hover/focus action |
| `--website-blue-soft` | `#DBEAFE` | Light action background |
| `--website-teal` | `#14B8A6` | Secondary accent and supporting highlights |

### Semantic Palette

| Token | Dark value | Light value | Use |
|---|---|---|---|
| `--website-success` | `#22C55E` | `#16A34A` | Positive state and verified status |
| `--website-warning` | `#F59E0B` | `#D97706` | Caution and incomplete setup |
| `--website-error` | `#EF4444` | `#DC2626` | Errors and destructive state |
| `--website-info` | `#38BDF8` | `#0284C7` | Informational state |

Rules:

- Text must meet WCAG AA contrast for its size and weight.
- Color must never be the only indicator of state.
- Red/green must be paired with text or an icon label.
- Do not use success green to imply profit or guaranteed performance.
- Do not use warning/error colors for marketing urgency.

### Token Naming

Components use semantic tokens, not raw hex values:

```text
--color-bg-page
--color-bg-surface
--color-bg-elevated
--color-text-primary
--color-text-secondary
--color-border
--color-action-primary
--color-action-primary-hover
--color-success
--color-warning
--color-error
```

The mapping from semantic tokens to brand values must live in one Website theme layer.

## Typography

### Font Families

Proposed stack:

- Display/headings: `Space Grotesk`, fallback `Inter`, system sans-serif
- Body/UI: `Inter`, fallback `system-ui`, sans-serif
- Numeric/technical accents: `IBM Plex Mono`, fallback `ui-monospace`, monospace

Font loading must be local or use an approved provider with `font-display: swap`. Do not block first paint on font downloads.

### Type Scale

| Token | Size | Line height | Use |
|---|---:|---:|---|
| `text-xs` | 12px | 18px | Labels, metadata |
| `text-sm` | 14px | 21px | Supporting copy, controls |
| `text-md` | 16px | 24px | Body text |
| `text-lg` | 18px | 27px | Lead body and card headings |
| `text-xl` | 20px | 28px | Section subheading |
| `text-2xl` | 24px | 32px | Card/section heading |
| `text-3xl` | 30px | 38px | Small hero heading |
| `text-4xl` | 36px | 44px | Tablet hero heading |
| `text-5xl` | 48px | 56px | Desktop hero heading |
| `text-6xl` | 60px | 68px | Large desktop display only |
|

Typography rules:

- Body text max width: 68ch.
- Hero heading max width: 12-16 words per line where possible.
- Use sentence case for navigation and controls.
- Use uppercase only for short labels or technical eyebrow text.
- Do not use more than two display weights on one page.
- Arabic content requires RTL-aware line height and alignment review.

## Spacing and Grid

### Spacing Scale

Use a 4px base scale:

```text
4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128
```

### Layout Grid

| Viewport | Container | Columns | Gutter |
|---|---:|---:|---:|
| Mobile | fluid minus 32px | 4 | 16px |
| Small tablet | fluid minus 48px | 8 | 20px |
| Desktop | max 1200px | 12 | 24px |
| Wide desktop | max 1280px | 12 | 32px |

Rules:

- Section vertical padding: 64px mobile, 96px desktop, 128px for hero/major transitions.
- Keep primary content inside the container; full-bleed backgrounds may extend beyond it.
- Avoid layouts that depend on fixed viewport height.
- Use CSS grid for page structure and flexbox for component alignment.

### Responsive Breakpoints

```text
sm: 640px
md: 768px
lg: 1024px
xl: 1280px
2xl: 1536px
```

The design must be usable at 320px width and 200% browser zoom.

## Buttons

### Variants

- Primary: filled blue action for the main page CTA
- Secondary: outlined action for alternate path
- Tertiary: text/link action for low-emphasis navigation
- Ghost: transparent action on dark surfaces
- Destructive: reserved for irreversible account actions; not used on marketing pages

### Sizes

| Size | Height | Horizontal padding | Use |
|---|---:|---:|---|
| Small | 32px | 12px | Compact utility action |
| Medium | 40px | 16px | Default CTA/control |
| Large | 48px | 20px | Hero and pricing CTA |

Button states:

- default
- hover
- focus-visible
- active
- disabled
- loading
- success/error feedback where relevant

Rules:

- Every button must have a visible focus state.
- Button labels must describe the destination/action.
- Do not use “Start Trading” if the action only opens registration.
- Do not use loading spinners without preserving the label context.

## Cards

### Card Tokens

- Default radius: 12px
- Featured pricing radius: 16px
- Border: 1px semantic border token
- Padding: 20px mobile, 24px desktop
- Shadow: subtle elevation only; no heavy glow by default
- Hover: border/accent shift only when the card is interactive

### Card Rules

- A card must have one clear purpose.
- Do not nest cards inside cards unless the inner block is a documented component.
- Interactive cards must expose keyboard focus and a clear target.
- Pricing cards must not visually imply that the most expensive plan is always the correct choice.

## Inputs, Forms, and Tables

### Inputs

States:

- default
- hover
- focus-visible
- filled
- disabled
- invalid
- valid
- loading

Rules:

- Labels are always visible; placeholders are not labels.
- Error text appears adjacent to the field and is announced accessibly.
- Password fields must have a reveal control with an accessible label.
- Contact forms require anti-abuse protection before production.

### Tables

Website tables are limited to documentation/pricing comparisons.

- Use semantic `<table>` elements for tabular data.
- Include a caption or accessible name.
- Keep columns readable on mobile; allow intentional horizontal scrolling.
- Do not copy dashboard trading tables into the Website.
- Use a comparison grid instead of a table when the content is marketing-oriented.

## Radius, Shadows, and Borders

### Radius

```text
radius-sm: 6px
radius-md: 10px
radius-lg: 14px
radius-xl: 20px
radius-pill: 999px
```

Use pill radius only for tags, badges, or compact controls. Do not make every container a pill.

### Shadows

```text
shadow-sm: 0 1px 2px rgba(2, 8, 23, 0.08)
shadow-md: 0 8px 24px rgba(2, 8, 23, 0.14)
shadow-lg: 0 20px 50px rgba(2, 8, 23, 0.18)
```

Dark surfaces should prefer border/elevation contrast over large black shadows.

### Borders

- Default: 1px solid semantic border
- Focus: 2px visible outline or equivalent accessible ring
- Featured: accent border plus non-color indicator
- Do not use hairline borders that disappear on mobile or high-density screens.

## Icons and Imagery

- Use one approved SVG icon family.
- Prefer inline SVG or a documented icon package; do not mix emoji, random icon fonts, and unrelated SVG styles.
- Standard icon sizes: 16px, 20px, 24px, 32px.
- Icons used as controls require accessible labels.
- Decorative icons must be hidden from assistive technology.
- Product imagery should show interface clarity, risk controls, and workflow confidence.
- Do not use fake broker screenshots, fake profit charts, or unverified performance visuals.

## Animation

### Timing

```text
fast: 120ms
standard: 180ms
emphasis: 260ms
```

Allowed:

- menu open/close
- accordion expansion
- button state transition
- subtle section reveal when it does not block reading
- hover/focus transitions

Not allowed:

- autoplay trading-chart animations implying live profit
- animations that delay content access
- parallax that harms mobile performance
- looping attention-grabbing effects on primary CTAs

Respect `prefers-reduced-motion: reduce` by disabling non-essential movement.

## Theme

Website default: dark-first brand presentation using the navy/blue palette.

Light theme is allowed only if:

- all contrast checks pass;
- every component has a tested light token;
- the theme switch is documented in Navigation/Accessibility;
- it does not couple Website theme state to the frozen dashboard `ThemeProvider`.

The Website theme must be self-contained. Do not import `admin_dashboard/components/ThemeProvider.tsx` into the future Website app.

## Localization

The content architecture must support:

- English
- Arabic with RTL layout
- French
- Spanish

Final language launch scope is an approval gate. Translation strings must live outside components. Do not concatenate translated text inside page JSX.

## Design Review Checklist

Before implementation approval:

- logo variants approved
- color values approved
- font licensing/source approved
- English copy approved
- Arabic/FR/ES launch decision recorded
- legal copy owners identified
- pricing content owner identified
- image/icon source approved
- mobile and accessibility targets accepted
