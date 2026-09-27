# Website Sprint W1 Report

## Status

- Sprint: W1 Website Foundation
- Status: Implementation and browser visual QA complete; explicit human sign-off pending
- Content pages: not implemented
- Backend V2 changes: none
- Client/Admin dashboard changes: none
- API calls from Website components: none

## Implemented Foundation

Created a separate Website app under `website/` with:

- standalone Next.js package and build configuration
- centralized Website design tokens
- dark/light theme toggle
- responsive Website shell
- skip link and semantic main/header/footer structure
- desktop navigation
- mobile navigation menu
- mobile Escape close and focus containment behavior
- portal URL configuration
- reusable Logo, Icon, Button, LinkButton, Card, and FormField primitives
- SectionHeading, FeatureCard, FeatureGrid, StatsStrip, and PricingCard components
- foundation preview composition
- responsive grid and typography tokens
- reduced-motion support
- focus-visible and form accessibility states

## Files

### App Foundation

- `website/package.json`
- `website/package-lock.json`
- `website/tsconfig.json`
- `website/next-env.d.ts`
- `website/next.config.ts`
- `website/app/layout.tsx`
- `website/app/page.tsx`
- `website/app/globals.css`

### Configuration

- `website/lib/navigation.ts`
- `website/lib/urls.ts`

### Layout

- `website/components/layout/WebsiteShell.tsx`
- `website/components/layout/WebsiteHeader.tsx`
- `website/components/layout/WebsiteFooter.tsx`
- `website/components/layout/ThemeToggle.tsx`

### Primitives and Components

- `website/components/primitives/`
- `website/components/content/`
- `website/components/commerce/`
- `website/components/foundation/FoundationPreview.tsx`

### Visual QA Harness

- `website/qa/website_w1_visual_qa.py`
- `website/qa/w1_visual_results.json`
- `website/qa/screenshots/w1/dark/`
- `website/qa/screenshots/w1/light/`

## Rule Verification

| Rule | Result |
|---|---|
| Desktop/tablet/mobile CSS paths defined before content pages | PASS |
| Shared components instead of page-specific copies | PASS |
| Page is composition-only | PASS |
| Design tokens centralized in `app/globals.css` | PASS |
| No inline styles in components | PASS |
| No raw hex colors in components | PASS |
| No API/business logic in components | PASS |
| Dark/light theme foundation | PASS |
| Reduced-motion support | PASS |
| Keyboard/focus foundation | PASS |

## Verification

- `npx tsc --noEmit`: PASS
- `npm run build`: PASS
- Browser visual QA: **198 PASS / 0 FAIL**
- Viewports: `1440x900`, `1280x800`, `1024x768`, `768x1024`, `390x844`, `375x812`
- Themes: dark and light
- HTTP/browser load on `/`: `200` for all viewport/theme combinations
- Static component checks: PASS

Screenshots are stored under `website/qa/screenshots/w1/{dark,light}/`. Representative desktop, tablet, and mobile screenshots were inspected after the automated pass.

### Accessibility Findings

- Semantic header, nav, main, footer landmarks: PASS
- Skip link: PASS
- Button/link accessible names: PASS
- Keyboard focus visibility: PASS
- Mobile menu `Escape` close: PASS after fix
- Mobile menu focus containment and focus return: PASS after fix
- Reduced-motion media behavior: PASS

### Responsive Findings

- No horizontal overflow at all six viewport sizes: PASS
- Desktop navigation at the `1024px` breakpoint: PASS
- Mobile navigation below the `1024px` breakpoint: PASS
- Cards stack correctly on mobile: PASS
- Stats strip stacks correctly on mobile: PASS
- Mobile CTA/header fit: PASS after compact-logo fix
- Footer remains readable and usable: PASS

### Visual Issues Found and Fixed

1. Mobile header wordmark and primary CTA competed for width, causing the CTA label to wrap. Fixed by using the approved compact logo mark below `640px`.
2. Mobile menu did not close on `Escape` and did not contain tab focus. Fixed in `WebsiteHeader` with Escape handling, focus return, and tab cycling.

The `1024px` mobile-menu failure was a QA threshold mismatch, not an application defect; the design system defines `lg: 1024px` as the desktop-navigation boundary.

## Dependency Note

The Website uses `next@15.5.23`. `npm audit --omit=dev` still reports high transitive advisories in PostCSS/sharp; automatic remediation requires the breaking Next 16 upgrade. `npm audit fix --force` was intentionally not run. This is a dependency follow-up, not a component or architecture change.

## Not Implemented

- Landing content
- Pricing page
- Features page
- FAQ page
- Documentation pages
- Contact page/submission
- Terms, privacy, risk disclosure content
- Authentication integration
- Billing
- Analytics/cookie consent
- Lighthouse W5 gate

## Remaining Issues

- `npm audit --omit=dev` reports three high transitive PostCSS/sharp advisories; the automatic fix requires breaking Next 16 and was not forced.
- Lighthouse is intentionally deferred to Sprint W5.
- Cross-browser review beyond Chromium remains a later manual check.
- Final public content, logo assets, fonts, and copy are still not implemented.

## Exit Decision

Automated browser visual/UX QA: **PASS**. W1 is ready for explicit human sign-off. Do not start W2 content pages until:

- design tokens and logo are visually approved;
- desktop/tablet/mobile screenshots are reviewed;
- the dependency advisory decision is recorded;
- W1 is explicitly marked approved.
