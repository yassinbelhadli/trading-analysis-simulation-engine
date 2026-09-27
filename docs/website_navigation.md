# Website Navigation Map

## Status

- Phase: 2.1 Website
- Status: Approved navigation map; W1 shell navigation implemented, content routes pending
- Source of truth: this document
- Any navigation change requires updating this document first

## Primary Route Tree

```text
/
├── /pricing
├── /features
├── /faq
├── /docs
│   └── /docs/{slug}
├── /contact
├── /terms
├── /privacy
└── /risk-disclosure
```

Portal/auth destinations are separate surfaces:

```text
Website
  ├── Client Login       -> app.ictfundedeapro.com/client/login
  ├── Create Account     -> app.ictfundedeapro.com/client/register
  ├── Forgot Password    -> app.ictfundedeapro.com/client/forgot-password
  └── Staff Login        -> admin.ictfundedeapro.com/login
```

## Desktop Header

Recommended order:

```text
Logo
  Features
  Pricing
  FAQ
  Documentation
  Contact
  [Log in]
  [Create account]
```

Rules:

- Logo links to `/`.
- `Create account` is the primary header CTA.
- `Log in` links to the Client Portal, not staff login.
- Staff login is not shown as a primary marketing CTA.
- Header remains visible or becomes compact on scroll according to the approved design system.
- Active navigation state is clear but not color-only.

## Mobile Header

```text
Logo                         Menu button
                              |
                              +-- Features
                              +-- Pricing
                              +-- FAQ
                              +-- Documentation
                              +-- Contact
                              +-- Log in
                              +-- Create account
```

Requirements:

- menu button has an accessible label;
- menu traps focus while open where appropriate;
- Escape closes the menu;
- selecting a link closes the menu;
- the primary CTA remains visually distinct;
- no horizontal overflow at 320px width.

## Footer Map

```text
Product
  Features
  Pricing
  How it works

Resources
  FAQ
  Documentation
  Contact

Portals
  Client Login
  Create Account

Legal
  Terms
  Privacy
  Risk Disclosure

Footer bottom
  Copyright
  Language selector
  Approved social/support links
```

Do not link to admin or owner portals from the primary public navigation. Staff/owner entry points are separate operational surfaces.

## Page-Level Navigation

### Landing `/`

Primary flow:

```text
Hero CTA -> Create Account
Feature section -> Features
Plan preview -> Pricing
FAQ preview -> FAQ
Final CTA -> Create Account
```

### Pricing `/pricing`

Primary flow:

```text
Plan CTA -> Create Account or approved contact path
Compare features -> Features
Questions -> FAQ / Contact
Existing client -> Client Login
```

Until Billing is implemented, pricing CTAs must not simulate checkout or subscription activation.

### Features `/features`

Primary flow:

```text
Feature content -> Pricing
Feature content -> Documentation
Final CTA -> Create Account
```

### FAQ `/faq`

Primary flow:

```text
FAQ answer -> relevant Documentation article
Unanswered question -> Contact
Final CTA -> Create Account
```

### Documentation `/docs`

Primary flow:

```text
Docs index -> /docs/{slug}
Article -> related article
Article -> Contact
Article -> Client Login when account action is required
```

Documentation breadcrumbs:

```text
Home / Documentation / Article
```

### Contact `/contact`

Primary flow:

```text
Contact details/form -> support channel
Account issue -> Client Login
Billing question -> Contact/support path until Billing exists
```

No contact submission API is implied by this map.

### Legal Pages

Legal pages include a consistent footer and return to the last public page or `/`.

```text
Terms <-> Privacy <-> Risk Disclosure
```

Legal pages must not contain unapproved product promises or payment terms.

## Authentication Redirect Map

Phase 2.1 links only; Phase 2.2 implements the flows:

```text
/client/register
  -> POST /auth/register
  -> /client/verify-email or verification instruction

/client/login
  -> POST /auth/login
  -> app.ictfundedeapro.com/client/dashboard

/client/forgot-password
  -> POST /auth/forgot-password
  -> /client/reset-password

/client/reset-password
  -> POST /auth/reset-password
  -> /client/login
```

Failure rules:

- SMTP unavailable must show a clear support path.
- Invalid credentials must show a safe generic message.
- No token is placed in a URL unless the existing backend contract requires a safe, expiring verification value.
- Admin login redirects to the Admin Portal only.

## Breadcrumb and Active-State Rules

- Home `/` has no breadcrumb.
- Documentation pages show breadcrumbs.
- Legal pages may show a simple “Back to Website” link.
- Active header state is based on route ownership, not substring matches that mark unrelated pages active.
- External portal links do not appear active as Website pages after navigation away.

## 404 and Error Navigation

Unknown public Website route:

```text
404
  -> Back to home
  -> View documentation
  -> Contact support
```

Public content failure:

```text
Readable error state
  -> Retry if applicable
  -> Return home
```

Do not expose stack traces, API URLs, database details, or internal service names.

## Navigation Ownership

| Link/category | Owner | May link to |
|---|---|---|
| Public product nav | Website | Website pages |
| Client CTA | Website/Auth | Client auth/portal |
| Staff entry | Admin/Auth | Admin login |
| Owner entry | Owner phase | Owner login/portal after policy approval |
| Billing CTA | Billing phase | Approved checkout only |
| Documentation | Website content | Static docs and approved portal help |
| Legal | Website/legal owner | Legal pages |

## Navigation QA

- Every header/footer link resolves.
- Every CTA has an approved destination.
- Client login/register links point to the Client Portal.
- Staff login is not accidentally routed to client login.
- No Website navigation calls `/api/admin/*` or `/admin/*`.
- External portal links preserve the intended origin/subdomain.
- Mobile menu keyboard/focus behavior passes.
- Breadcrumbs match the route tree.
- 404 links return to valid public pages.

## Change Gate

Before adding a new Website route or navigation item, document:

- goal and user journey;
- owning page/component;
- content source;
- API dependency, if any;
- authentication/permission boundary;
- SEO behavior;
- mobile behavior;
- QA and exit criteria.
