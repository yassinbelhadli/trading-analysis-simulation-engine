# Website Component Library

## Status

- Phase: 2.1 Website
- Status: Approved component contract; W1 foundation subset implemented
- Rule: each component is designed once and reused across Website pages
- Components must not import backend modules or own business logic

## Component Principles

1. Components own presentation, interaction, accessibility, and visual states.
2. Page files compose components; they do not duplicate component markup.
3. API/auth calls live in dedicated client modules, not visual components.
4. Content is passed through typed props or content modules, not embedded repeatedly in JSX.
5. Every interactive component defines keyboard, focus, disabled, loading, and error behavior.
6. Components use Website design tokens from `website_design_system.md`.
7. A component is added only when it has a real consumer; avoid speculative component catalogs.

## Component Inventory

| Component | Purpose | Required variants |
|---|---|---|
| `WebsiteShell` | Global page frame and theme context | dark, light if approved |
| `WebsiteHeader` | Desktop navigation, brand, CTA, language | expanded, compact, scrolled |
| `MobileMenu` | Mobile navigation drawer/menu | closed, open, focus-trapped |
| `WebsiteFooter` | Product, resources, legal, contact links | default |
| `HeroSection` | Page opening statement and primary CTA | landing, inner-page |
| `SectionHeading` | Eyebrow, title, description hierarchy | left, centered |
| `Button` | Shared action control | primary, secondary, tertiary, ghost |
| `LinkButton` | Navigation styled as action | internal, external, portal |
| `Badge` | Small semantic label | info, success, warning, neutral |
| `FeatureCard` | Product capability presentation | icon, metric, compact |
| `FeatureGrid` | Responsive feature composition | 2, 3, 4 columns |
| `PricingCard` | Plan presentation and CTA | standard, featured, unavailable |
| `PricingComparison` | Plan comparison content | grid, table-like |
| `StatsStrip` | Small proof/metric presentation | 2, 3, 4 items |
| `CTASection` | Conversion section near page end | primary, secondary |
| `FaqAccordion` | Expandable FAQ content | single-open, multi-open |
| `DocsSidebar` | Documentation navigation | desktop, mobile |
| `Breadcrumbs` | Documentation hierarchy | one or more levels |
| `DocsArticle` | Static article body and metadata | standard, long-form |
| `ContactForm` | Contact/support request UI | idle, submitting, success, error |
| `NewsletterForm` | Optional email capture | idle, submitting, success, error |
| `CookieBanner` | Consent notice if tracking is approved | visible, dismissed |
| `TestimonialCard` | Approved customer statement | quote, compact |
| `Logo` | Brand asset and variants | dark, light, compact, wordmark |
| `Icon` | Central icon wrapper | decorative, labelled |
| `ResponsiveImage` | Optimized image with fallback | eager, lazy |
| `EmptyState` | No-content/coming-soon state | docs, pricing, contact |
| `ErrorState` | Public page failure state | inline, full-page |

## Component Contracts

### WebsiteShell

Responsibilities:

- theme token provider
- global font and body defaults
- skip link
- page-width container
- metadata hooks

Must not:

- read admin/client settings
- load an authenticated token
- call API endpoints during static page render

### WebsiteHeader

Required content:

- approved logo
- navigation links from `website_navigation.md`
- primary Client Portal CTA
- language selector when localization is approved
- mobile menu trigger

Accessibility:

- semantic `<header>` and `<nav>`
- labelled mobile menu button
- visible focus state
- current page state
- keyboard-close behavior for mobile menu

### HeroSection

Props contract:

- eyebrow: optional short label
- title: required
- description: optional
- primaryAction: optional link action
- secondaryAction: optional link action
- visual: optional approved media slot

Rules:

- exactly one primary message;
- no unsupported performance claims;
- visual slot must have an image description or be decorative explicitly.

### PricingCard

Props contract:

- plan name
- price label
- billing label
- account limit
- feature list
- CTA label/destination
- featured state
- availability state

Rules:

- do not call a contact CTA “Subscribe” unless Billing exists;
- unavailable plans show why and a safe next step;
- plan comparison must not expose internal license keys or admin settings;
- featured styling cannot rely on color alone.

### FeatureCard

Props contract:

- icon
- title
- description
- optional link
- optional proof/metric only if approved

Feature cards must describe implemented or explicitly planned capabilities accurately.

### FaqAccordion

Requirements:

- native button controls
- `aria-expanded`
- `aria-controls`
- keyboard operation
- deep-linkable IDs when useful
- content remains searchable in the DOM

### ContactForm

Phase 2.1 options:

- static contact details/link; or
- a form that is visually specified but not submitted until a backend contract exists

Do not invent a contact API or store personal data during Website implementation.

### CookieBanner

Do not implement until analytics/tracking is approved. A decorative privacy link is not a consent system.

### NewsletterForm

Do not implement submission until an approved provider, consent model, unsubscribe flow, and storage boundary exist. A static “contact us” alternative is acceptable in Phase 2.1.

## Component State Matrix

Every interactive component must define:

| State | Requirement |
|---|---|
| Default | Clear visual hierarchy and usable contrast |
| Hover | Non-essential enhancement; must not be the only affordance |
| Focus | Visible keyboard focus ring |
| Active | Clear pressed/navigation state |
| Disabled | Explain unavailable state where useful |
| Loading | Preserve context and prevent duplicate submissions |
| Success | Human-readable confirmation |
| Error | Human-readable recovery path |
| Empty | Explain what is missing and what to do next |
| Reduced motion | Remove non-essential animation |

## Composition Rules

```text
WebsiteShell
  -> WebsiteHeader
  -> PageContainer
       -> SectionHeading
       -> HeroSection / FeatureGrid / PricingComparison / DocsArticle
       -> CTASection
  -> WebsiteFooter
```

Page-specific content belongs in page/content modules. Shared behavior belongs in the component library.

Do not create separate copies such as `LandingButton`, `PricingButton`, and `DocsButton` when `Button` variants are sufficient.

## Component Directory Proposal

```text
website/components/
  layout/
    WebsiteShell.tsx
    WebsiteHeader.tsx
    WebsiteFooter.tsx
    MobileMenu.tsx
    PageContainer.tsx
  navigation/
    Breadcrumbs.tsx
    DocsSidebar.tsx
  content/
    HeroSection.tsx
    SectionHeading.tsx
    FeatureCard.tsx
    FeatureGrid.tsx
    StatsStrip.tsx
    TestimonialCard.tsx
    DocsArticle.tsx
    FaqAccordion.tsx
  commerce/
    PricingCard.tsx
    PricingComparison.tsx
  forms/
    ContactForm.tsx
    NewsletterForm.tsx
  primitives/
    Button.tsx
    LinkButton.tsx
    Badge.tsx
    Logo.tsx
    Icon.tsx
    ResponsiveImage.tsx
    EmptyState.tsx
    ErrorState.tsx
  consent/
    CookieBanner.tsx
```

This is a logical structure. Do not create directories or empty components before the relevant Website sprint is approved.

## QA Contract

Every implemented component must have:

- desktop and mobile verification;
- keyboard/focus verification for interactive behavior;
- reduced-motion verification where animated;
- light/dark verification if both themes are shipped;
- content overflow verification;
- no API/business logic hidden inside presentation code;
- no duplicate component implementation elsewhere in the Website.

## Exit Criteria

The component library is ready for implementation only when:

- design tokens are approved;
- logo/font/icon decisions are approved;
- component variants are limited to real page consumers;
- navigation and route ownership are approved;
- authentication and billing boundaries are documented;
- the first Website sprint has explicit files, QA, and exit criteria.
