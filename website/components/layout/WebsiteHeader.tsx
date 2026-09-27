"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { portalUrls } from "@/lib/urls";
import { primaryNav } from "@/lib/navigation";
import Button from "@/components/primitives/Button";
import Icon from "@/components/primitives/Icon";
import LinkButton from "@/components/primitives/LinkButton";
import Logo from "@/components/primitives/Logo";
import ThemeToggle from "@/components/layout/ThemeToggle";

export default function WebsiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLElement>(null);
  const mobileToggleRef = useRef<HTMLButtonElement>(null);
  const isCurrent = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  useEffect(() => {
    if (!open) return;
    const menu = mobileMenuRef.current;
    if (!menu) return;
    const focusable = Array.from(
      menu.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'),
    );
    focusable[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        mobileToggleRef.current?.focus();
        return;
      }
      if (event.key !== "Tab" || focusable.length < 2) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <header className="website-header">
      <div className="container">
        <div className="website-header__inner">
          <Logo />
          <nav className="website-header__nav" aria-label="Primary navigation">
            {primaryNav.map((item) => (
              <Link
                key={item.href}
                className="website-header__link"
                href={item.href}
                aria-current={isCurrent(item.href) ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="website-header__actions">
            <ThemeToggle />
            <LinkButton href={portalUrls.clientLogin} variant="secondary" size="medium">Log in</LinkButton>
            <LinkButton href={portalUrls.clientRegister} variant="primary" size="medium">Create account</LinkButton>
            <Button
              className="website-header__mobile-toggle button--icon"
              variant="ghost"
              size="medium"
              ref={mobileToggleRef}
              onClick={() => setOpen((current) => !current)}
              aria-expanded={open}
              aria-controls="website-mobile-menu"
              aria-label={open ? "Close navigation menu" : "Open navigation menu"}
            >
              <Icon name={open ? "close" : "menu"} size={20} />
            </Button>
          </div>
        </div>
        <nav
          id="website-mobile-menu"
          ref={mobileMenuRef}
          className="website-header__mobile-panel"
          data-open={open}
          aria-label="Mobile navigation"
        >
          {primaryNav.map((item) => (
            <Link
              key={item.href}
              className="website-header__mobile-link"
              href={item.href}
              aria-current={isCurrent(item.href) ? "page" : undefined}
              onClick={() => setOpen(false)}
            >
              {item.label}
            </Link>
          ))}
          <a className="website-header__mobile-link" href={portalUrls.clientLogin} onClick={() => setOpen(false)}>Log in</a>
          <a className="button button--primary button--large" href={portalUrls.clientRegister} onClick={() => setOpen(false)}>Create account</a>
        </nav>
      </div>
    </header>
  );
}
