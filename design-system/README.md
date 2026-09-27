# Design System V2 — Shared Component Layer

Cross-portal design system for the ICT Funded EA Pro ecosystem
(Website, Client Portal, Admin Portal, Owner Portal).

## Structure

```
design-system/
  variables.css      # V2 tokens + legacy aliases (--bg-*, --accent, ...)
  tokens.css         # Tailwind v4 @theme mapping (@import variables.css first)
  globals.css        # base element styles, focus rings, scrollbars, helpers
  components/
    Icon.tsx         # stroke icon set (one consistent family)
    ui.tsx           # Button, Card, StatCard, Badge, PageHeader, EmptyState,
                     # Skeleton, SectionLabel, TextField, SelectField, Table,
                     # Td, StatusPill
    Modal.tsx        # Modal + ConfirmDialog (typed confirmation support)
    Toast.tsx        # ToastProvider / useToast (success, info, warn, error)
    AppShell.tsx     # AppSidebar (grouped nav), AppTopbar (mobile drawer),
                     # AppShell layout
    BrandLogo.tsx    # official logo (white chip on dark surfaces)
```

## Wiring into a Next.js app

1. `public/` — copy `media/brand/logo-transparent.png -> public/logo.png`,
   `favicon.ico -> public/favicon.ico` (already done for all 4 apps).

2. Fonts (per app, in `app/layout.tsx`):
   ```ts
   import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
   const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display" });
   const body = Inter({ subsets: ["latin"], variable: "--font-body" });
   const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });
   // <html className={`${display.variable} ${body.variable} ${mono.variable}`}>
   ```

3. CSS: in the app's `globals.css`:
   ```css
   @import "../../design-system/tokens.css";   /* variables + tailwind theme */
   @import "../../design-system/globals.css";  /* base styles */
   ```
   (Adjust the relative path per app. `tokens.css` contains
   `@source "../design-system/components"` so Tailwind scans shared components.)

4. Wrap the app in `<ToastProvider>` (root layout, client boundary).

## Usage

- Icons: `<Icon name="dashboard" className="h-4 w-4" />` — never use emoji.
- Buttons: `<Button variant="primary|secondary|danger|ghost|success" size="sm|md|lg">`
- Confirm dangerous actions: `<ConfirmDialog ... tone="danger" />`
- Contract gaps (no backend endpoint): `<EmptyState variant="gap" ... />`
  with "Not available / Backend integration required" copy — never invent
  controls for missing backend capabilities.

## Palette (dark first)

- Foundation: `#0A0C10` base / `#11151C` raised / `#161B24` overlay
- Primary (goblin green): `#12B76A` (dark) — utility `bg-brand-500`
- Secondary (tech blue): `#2F7BF6` — utility `text-tech-400`
- Ink: `#E6EAF0` / `#9AA6B5` / `#5C6B7E` (primary / soft / muted)
- Semantic: ok `#16A34A`, warn `#F59E0B`, danger `#EF4444`, info `#2F7BF6`

Legacy variables (`--bg-card`, `--text-primary`, `--accent`, ...) resolve to
the V2 palette so older portal pages render correctly until restyled.
