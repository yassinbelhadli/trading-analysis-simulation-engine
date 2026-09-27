"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "./Icon";
import { Button, TextField, type ButtonVariant } from "./ui";

/* ==========================================================================
   Design System V2 — Modal & ConfirmDialog
   ========================================================================== */

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  icon?: "alert" | "info" | "success" | "danger";
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}

const sizes = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl" };

const iconStyles = {
  alert: "bg-warn/10 text-warn",
  info: "bg-tech-tint text-tech-400",
  success: "bg-brand-tint text-brand-400",
  danger: "bg-danger/10 text-danger",
};

export function Modal({ open, onClose, title, subtitle, icon, children, footer, size = "md" }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === "string" ? title : undefined}
    >
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        className={`relative w-full ${sizes[size]} bg-overlay border border-line-strong rounded-xl shadow-pop
          flex flex-col max-h-[85vh] animate-in`}
        style={{ animation: "dsModalIn 0.16s ease-out" }}
      >
        <style>{`@keyframes dsModalIn { from { opacity: 0; transform: translateY(8px) scale(0.98); } to { opacity: 1; transform: none; } }`}</style>
        <header className="flex items-start gap-3 px-5 pt-5 pb-4 border-b border-line">
          {icon && (
            <span className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${iconStyles[icon]}`}>
              <Icon name={icon === "alert" ? "alert-triangle" : icon === "danger" ? "x-circle" : icon === "success" ? "check-circle" : "info"} className="h-4.5 w-4.5" />
            </span>
          )}
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold leading-6">{title}</h2>
            {subtitle && <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="h-7 w-7 rounded-md flex items-center justify-center text-ink-muted hover:text-ink hover:bg-hover transition-colors"
          >
            <Icon name="close" className="h-4 w-4" />
          </button>
        </header>
        <div className="px-5 py-4 overflow-y-auto">{children}</div>
        {footer && <footer className="px-5 py-4 border-t border-line flex justify-end gap-2">{footer}</footer>}
      </div>
    </div>
  );
}

/* ---------------------------- ConfirmDialog ----------------------------- */

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ButtonVariant;
  requireText?: string; // if set, user must type this before confirming
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "primary",
  requireText,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");
  const match = !requireText || typed === requireText;

  useEffect(() => {
    if (open) setTyped("");
  }, [open]);

  const handleConfirm = () => {
    if (match) onConfirm();
  };

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      icon={tone === "danger" ? "danger" : "alert"}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={tone} onClick={handleConfirm} loading={loading} disabled={!match}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {description && <p className="text-sm text-ink-soft">{description}</p>}
      {requireText && (
        <div className="mt-4">
          <p className="text-xs text-ink-muted mb-2">
            Type <code className="font-mono text-warn">{requireText}</code> to confirm.
          </p>
          <TextField
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={requireText}
            autoFocus
          />
        </div>
      )}
    </Modal>
  );
}
