# Phase 2.1 Website Specification

## Status

- Phase: 2.1 Website
- Status: W1 foundation implemented; W2 content not started
- Backend V2: frozen
- Next phase after this document: Phase 2.2 Authentication Integration
- This document is a scope contract, not permission to begin Dashboard work
- Required design references: `website_design_system.md`, `website_components.md`, `website_navigation.md`
- Implementation gate: all three design documents must be approved before Website components are written
- W1 implementation report: `website_w1_report.md`
- W1 visual QA report: `website_w1_report.md`

## Goal

Build the public product website for ICT Funded EA Pro.

The Website must explain the product, establish trust, present plans, answer common questions, and direct users to the existing authentication and client portal surfaces.

The Website is a public marketing/content surface. It is not a client dashboard, admin portal, owner portal, billing console, Telegram interface, or trading control surface.

## Scope

### Public Pages

| Route | Purpose |
|---|---|
| `/` | Landing page and primary conversion path |
| `/pricing` | Plans, limits, included features, and CTA |
| `/features` | Product capabilities and platform explanation |
| `/faq` | Common product, account, license, and support questions |
| `/docs` | Documentation index and getting-started content |
| `/docs/{slug}` | Static documentation article pages |
| `/contact` | Support/contact information and safe contact CTA |
| `/terms` | Terms of service |
| `/privacy` | Privacy policy |
| `/risk-disclosure` | Trading and capital-risk disclosure |

### Shared Website Elements

- Header and navigation
- Primary and secondary CTA components
- Pricing cards
- Feature sections
- FAQ accordion
- Documentation navigation
- Footer with legal links
- Language selector architecture
- Responsive mobile navigation
- SEO metadata and social preview metadata
- Accessible focus, keyboard, contrast, and semantic structure

### Authentication Entry Points

Phase 2.1 may display links to authentication, but the full authentication integration is Phase 2.2.

Required links:

- `Open Client Portal` -> `app.ictfundedeapro.com/client/login`
- `Create Client Account` -> `app.ictfundedeapro.com/client/register`
- `Client Forgot Password` -> `app.ictfundedeapro.com/client/forgot-password`
- Staff login must not be presented as the primary public CTA

## Out Of Scope

- Client Dashboard V2
- Admin Dashboard V2
- Owner Dashboard
- Billing checkout or payment provider integration
- Subscription creation or renewal
- License creation or activation
- MT4/MT5 account connection
- Telegram linking or notifications
- Trading signals, trades, risk controls, or engine status
- Backend V2 refactor
- New API routes
- Database schema changes
- CMS integration
- User-generated documentation editor
- Admin content management UI
- Realtime or WebSocket features
- Cache or event transport

If a requirement needs a new API, database field, permission, payment provider, or background worker, it is outside Phase 2.1 and must be recorded for a later phase.

## Backend Boundary

The Website must not import backend Python modules or call private APIs directly.

Phase 2.1 should require no API calls for static marketing/content pages. Pricing and feature content should use an explicitly approved website content source, not a direct import from `config`, `plans_config.py`, or database models.

The frozen API contracts remain available but unchanged:

- `/auth/*`
- `/api/client/*`
- `/api/admin/*`
- `/api/licenses/*`

Phase 2.2 may integrate the existing authentication endpoints without changing their request/response contracts:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/verify-email/confirm`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/refresh`
- `POST /auth/logout`

No new public pricing API is authorized by this document. If dynamic pricing is required, stop and propose a separate contract rather than adding an endpoint during implementation.

## Domain and Subdomain

Confirmed production domain context from `docs/platform_architecture.md`:

- `www.ictfundedeapro.com`: public Website
- `app.ictfundedeapro.com`: Client Portal
- `admin.ictfundedeapro.com`: Admin Portal
- `owner.ictfundedeapro.com`: future Owner Portal
- `api.ictfundedeapro.com`: API through the edge proxy

DNS ownership, canonical domain, brand spelling, and legal entity details must be confirmed before production deployment.

The Website must use configuration for portal URLs. Do not hardcode localhost or production URLs in components.

## Recommended Application Boundary

The Website should be a separate deployable Next.js application or an isolated monorepo app.

Recommended logical structure:

```text
website/
  app/
    page.tsx
    pricing/page.tsx
    features/page.tsx
    faq/page.tsx
    docs/page.tsx
    docs/[slug]/page.tsx
    contact/page.tsx
    terms/page.tsx
    privacy/page.tsx
    risk-disclosure/page.tsx
  components/
    WebsiteHeader.tsx
    WebsiteFooter.tsx
    PricingCard.tsx
    FeatureSection.tsx
    FaqItem.tsx
  content/
    pages/
    docs/
    plans.ts
  lib/
    urls.ts
    seo.ts
  public/
    images/
```

Do not place marketing pages inside `admin_dashboard/app/dashboard` or `admin_dashboard/app/client/dashboard`.

Shared visual tokens may be extracted later only if the extraction does not alter frozen portal behavior.

## Content Contract

### Landing Page Sections

1. Hero: clear product promise and primary CTA
2. Trust/value statement: funded-account capital protection and controlled automation
3. How it works: account, license, EA, monitoring
4. Feature highlights: risk, news filter, MT4/MT5 support, Telegram alerts
5. Supported platforms/brokers: only claims verified by the product
6. Plan preview with link to full pricing
7. FAQ preview
8. Final CTA
9. Footer/legal links

Marketing copy must not promise guaranteed profit, guaranteed funding, or risk-free trading.

### Pricing Page

Each plan card must define:

- plan name
- price display and billing period
- account limit
- supported platform claims
- included features
- support level
- CTA destination
- clear note that final billing behavior is not implemented until Phase 6

Until Billing is approved, CTAs must use a safe contact/waitlist/portal path. They must not pretend to complete payment.

### Documentation Page

Initial articles should be static and versioned:

- Getting started
- Account requirements
- MT4 versus MT5
- License activation
- Risk rules
- Telegram notifications
- EA installation
- Support and troubleshooting

Documentation must distinguish demo/test behavior from production behavior.

## Authentication Integration Boundary

Phase 2.2 is separate from Website implementation.

Authentication integration must:

- use the existing backend request/response contracts;
- preserve verification and password-reset behavior;
- show a clear SMTP failure state when verification email is unavailable;
- never expose tokens in URLs or page content;
- keep client and admin portal destinations separate;
- never call admin or owner APIs from public pages;
- include manual tests for register, verify, login, logout, forgot password, and reset password.

The current backend has SMTP configuration gaps. Phase 2.2 cannot be considered complete until a real non-production SMTP inbox receives verification and reset messages.

## Authentication and Permission Rules

Phase 2.1 public pages need no authenticated permission.

| Website action | Required boundary |
|---|---|
| Read landing/pricing/features/FAQ/docs | Public website content only |
| Open client login/register | Client auth entry |
| Open staff login | Explicit staff link, not primary CTA |
| View client data | Client Portal and client JWT only |
| View admin data | Admin Portal and admin permission only |
| View owner data | Owner Portal and future owner policy only |
| Start payment | Future Billing contract only |

The Website must never infer permissions from client-side state. Backend authorization remains authoritative after redirect.

## SEO and Accessibility

Every public page must have:

- unique title
- meta description
- canonical URL
- Open Graph title/description/image
- Twitter/social metadata where applicable
- semantic heading order
- keyboard navigation
- visible focus state
- sufficient color contrast
- descriptive link/button labels
- alt text for meaningful images
- responsive layout from mobile to desktop

Site-level requirements:

- `robots.txt`
- `sitemap.xml`
- favicon and social image
- structured data for Organization, Product/SoftwareApplication, FAQ, and Breadcrumbs where accurate
- no indexing of client/admin/owner portals or private API responses

Do not add analytics or marketing trackers until consent, privacy, and data-retention requirements are approved.

## Security and Data Rules

- No API keys, tokens, passwords, broker credentials, or license secrets in website source.
- No private database data in static page payloads.
- No decrypted settings or broker/account details in public pages.
- Contact forms must have rate limiting and abuse protection before production.
- Public assets must not expose private screenshots, reports, logs, or EA build paths.
- Download links must remain entitlement-gated through the existing client API.
- CORS and trusted origins are deployment configuration, not component logic.

## QA Plan

### Static/Build QA

- TypeScript compile passes.
- Production build passes.
- All public routes generate/render successfully.
- No dashboard or admin route is changed by Website work.
- No Backend V2 route count or response contract changes.

### Browser QA

- Desktop: Chrome/Edge latest supported versions.
- Mobile: iOS Safari and Android Chrome.
- Navigation works with keyboard.
- Mobile menu opens/closes and preserves focus.
- All CTA links reach the intended portal or contact destination.
- No horizontal overflow.
- Images have loading/fallback behavior.
- 404 and error states are readable.

### Content/SEO QA

- Every page has approved copy.
- No unsupported trading/profit claims.
- Legal links are present.
- Sitemap and robots rules are correct.
- Open Graph previews are valid.
- FAQ structured data matches visible FAQ content.

### Auth Handoff QA

Phase 2.2 separately verifies:

- register
- email verification
- login
- forgot password
- reset password
- logout
- client portal redirect
- SMTP-unavailable fallback

## Exit Criteria

Phase 2.1 is complete only when:

- all in-scope public pages exist and are responsive;
- Website content is approved;
- pricing claims are approved and do not imply unimplemented billing;
- legal pages are approved;
- SEO metadata, sitemap, robots, and structured data pass review;
- public pages call no private/admin/owner API;
- no Backend V2 contract changed;
- no database/engine/Telegram/billing implementation changed;
- TypeScript and production build pass;
- desktop/mobile manual QA passes;
- an implementation report lists files, routes, content source, QA, and remaining debt.

After Phase 2.1, stop and request approval before Phase 2.2 authentication integration.

## Dependencies and Approvals

Before implementation starts, approve:

- canonical domain and portal URLs;
- brand name, logo, colors, and typography;
- final plan names/pricing copy;
- supported broker/platform claims;
- contact/support destinations;
- legal entity and legal copy;
- language scope: English-only first or EN/AR/FR/ES together;
- Website application boundary: separate app versus approved isolated monorepo app;
- analytics/consent policy;
- whether pricing is static until Billing or requires a new public read contract.

## Freeze Rule

This Website phase must build on Backend V2. If implementation reveals a missing backend capability, record it as a separate approved contract/bug request. Do not reopen Backend V2 architecture during Website work.
