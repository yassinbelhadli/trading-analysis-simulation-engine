"use client";

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { Icon, type IconName } from "./Icon";

/* ==========================================================================
   Design System V2 — UI primitives (shared across Client / Admin / Owner).
   Uses Tailwind tokens: bg-base, bg-raised, text-ink, border-line, brand, ...
   ========================================================================== */

/* ------------------------------- Button -------------------------------- */

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "success";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  loading?: boolean;
}

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-brand-500 text-ink-inverse hover:bg-brand-400 active:bg-brand-700",
  secondary:
    "border border-line-strong text-ink hover:border-brand-500 hover:text-brand-400 bg-transparent",
  danger: "border border-danger/50 text-danger hover:bg-danger/10",
  success: "border border-ok/50 text-ok hover:bg-ok/10",
  ghost: "text-ink-soft hover:bg-hover hover:text-ink",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
  lg: "h-10 px-5 text-sm gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  icon,
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg font-medium whitespace-nowrap
        transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2
        focus-visible:outline-brand-500 disabled:opacity-50 disabled:pointer-events-none
        ${buttonVariants[variant]} ${buttonSizes[size]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <svg
          className="h-4 w-4 animate-spin"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
      ) : (
        icon && <Icon name={icon} className="h-4 w-4 shrink-0" />
      )}
      {children}
    </button>
  );
}

/* -------------------------------- Card --------------------------------- */

export interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: IconName;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  bodyClassName?: string;
  hover?: boolean;
}

export function Card({ title, subtitle, icon, actions, children, className = "", bodyClassName = "", hover = false }: CardProps) {
  return (
    <section
      className={`bg-raised border border-line rounded-xl overflow-hidden
        ${hover ? "ds-card-hover hover:border-line-strong" : ""} ${className}`}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 px-5 pt-4 pb-3 border-b border-line/60">
          <div className="flex items-center gap-2.5 min-w-0">
            {icon && <Icon name={icon} className="h-4.5 w-4.5 text-brand-400 shrink-0" />}
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-ink truncate">{title}</h3>
              {subtitle && <p className="text-xs text-ink-muted mt-0.5 truncate">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

/* ------------------------------ StatCard -------------------------------- */

export type StatTone = "default" | "green" | "blue" | "amber" | "red";

const statTones: Record<StatTone, string> = {
  default: "text-ink",
  green: "text-brand-400",
  blue: "text-tech-400",
  amber: "text-warn",
  red: "text-danger",
};

const statIconBg: Record<StatTone, string> = {
  default: "bg-hover text-ink-soft",
  green: "bg-brand-tint text-brand-400",
  blue: "bg-tech-tint text-tech-400",
  amber: "bg-warn/10 text-warn",
  red: "bg-danger/10 text-danger",
};

export interface StatCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  icon?: IconName;
  tone?: StatTone;
  mono?: boolean;
  className?: string;
}

export function StatCard({ label, value, sub, icon, tone = "default", mono = false, className = "" }: StatCardProps) {
  return (
    <div className={`bg-raised border border-line rounded-xl p-4 flex items-start justify-between gap-3 ${className}`}>
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-muted truncate">{label}</p>
        <p
          className={`mt-1.5 text-2xl leading-none font-semibold tracking-tight ${statTones[tone]} ${
            mono ? "font-mono" : "font-display"
          }`}
        >
          {value}
        </p>
        {sub && <p className="mt-1.5 text-xs text-ink-muted truncate">{sub}</p>}
      </div>
      {icon && (
        <span className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${statIconBg[tone]}`}>
          <Icon name={icon} className="h-4.5 w-4.5" />
        </span>
      )}
    </div>
  );
}

/* -------------------------------- Badge -------------------------------- */

export type BadgeTone = "green" | "blue" | "amber" | "red" | "gray";

const badgeTones: Record<BadgeTone, string> = {
  green: "bg-brand-tint text-brand-400 border-brand-500/30",
  blue: "bg-tech-tint text-tech-400 border-tech-500/30",
  amber: "bg-warn/10 text-warn border-warn/30",
  red: "bg-danger/10 text-danger border-danger/30",
  gray: "bg-hover text-ink-soft border-line-strong/60",
};

export interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}

export function Badge({ children, tone = "gray", className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap ${badgeTones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/* ----------------------------- PageHeader ------------------------------- */

export interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-ink-muted mt-1 max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------ EmptyState ------------------------------ */

export interface EmptyStateProps {
  icon: IconName;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  variant?: "empty" | "gap";
}

/** Contract-gap variant = "Not available / Backend integration required". */
export function EmptyState({ icon, title, description, action, variant = "empty" }: EmptyStateProps) {
  const isGap = variant === "gap";
  return (
    <div className="flex flex-col items-center justify-center text-center py-14 px-6">
      <span
        className={`h-12 w-12 rounded-xl flex items-center justify-center mb-4 ${
          isGap ? "bg-warn/10 text-warn" : "bg-hover text-ink-muted"
        }`}
      >
        <Icon name={isGap ? "plug" : icon} className="h-6 w-6" />
      </span>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="text-sm text-ink-muted mt-2 max-w-sm">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* ------------------------------ Skeleton -------------------------------- */

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-hover ${className}`} />;
}

/* ---------------------------- SectionLabel ------------------------------ */

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-muted mb-3">{children}</p>
  );
}

/* ------------------------------- Inputs --------------------------------- */

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  icon?: IconName;
  rightSlot?: ReactNode;
}

export function TextField({ label, hint, error, icon, rightSlot, className = "", id, ...rest }: TextFieldProps) {
  const inputId = id || rest.name || label;
  return (
    <div className={className}>
      {label && (
        <label htmlFor={inputId} className="block text-xs font-medium text-ink-soft mb-1.5">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <Icon name={icon} className="h-4 w-4 text-ink-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        )}
        <input
          id={inputId}
          className={`h-9 w-full rounded-lg border bg-input px-3 text-sm text-ink placeholder:text-ink-muted
            focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors
            ${icon ? "pl-9" : ""} ${rightSlot ? "pr-9" : ""}
            ${error ? "border-danger" : "border-line"}`}
          {...rest}
        />
        {rightSlot && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center">{rightSlot}</span>
        )}
      </div>
      {error ? (
        <p className="mt-1.5 text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-ink-muted">{hint}</p>
      ) : null}
    </div>
  );
}

export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  children: ReactNode;
}

export function SelectField({ label, className = "", children, ...rest }: SelectFieldProps) {
  return (
    <div className={className}>
      {label && <label className="block text-xs font-medium text-ink-soft mb-1.5">{label}</label>}
      <select
        className="h-9 w-full rounded-lg border border-line bg-input px-3 pr-8 text-sm text-ink
          focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors
          appearance-none bg-no-repeat"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235c6b7e' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E\")",
          backgroundPosition: "right 0.7rem center",
        }}
        {...rest}
      >
        {children}
      </select>
    </div>
  );
}

/* ------------------------------ ToggleRow ------------------------------- */

export function ToggleRow({
  label,
  checked,
  onChange,
  icon,
  disabled = false,
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
  icon?: IconName;
  disabled?: boolean;
}) {
  return (
    <label
      className={`flex items-center justify-between gap-3 rounded-lg border border-line px-4 py-3 transition-colors ${
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:border-line-strong"
      }`}
    >
      <span className="flex items-center gap-2.5 text-sm text-ink">
        {icon && <Icon name={icon} className="h-4 w-4 text-ink-muted" />}
        {label}
      </span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-brand-500"
      />
    </label>
  );
}

/* ------------------------------ Table ----------------------------------- */

export interface TableProps {
  columns: ReactNode[];
  children: ReactNode;
  className?: string;
}

export function Table({ columns, children, className = "" }: TableProps) {
  return (
    <div className={`overflow-x-auto -mx-5 px-5 ${className}`}>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-line">
            {columns.map((col, i) => (
              <th
                key={i}
                className="px-2 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted whitespace-nowrap first:pl-0 last:pr-0"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line/70">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({ children, mono = false, className = "" }: { children?: ReactNode; mono?: boolean; className?: string }) {
  return (
    <td className={`px-2 py-3 align-middle whitespace-nowrap text-ink first:pl-0 last:pr-0 ${mono ? "font-mono text-[13px]" : ""} ${className}`}>
      {children}
    </td>
  );
}

/* ----------------------------- StatusPill ------------------------------- */

export type Status = "active" | "inactive" | "pending" | "error" | "warning";

const statusMap: Record<Status, BadgeTone> = {
  active: "green",
  inactive: "gray",
  pending: "blue",
  error: "red",
  warning: "amber",
};

export function StatusPill({ status, children }: { status: Status; children: ReactNode }) {
  return (
    <Badge tone={statusMap[status]}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </Badge>
  );
}
