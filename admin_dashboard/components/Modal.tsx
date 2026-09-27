"use client";

import { Modal as DSModal } from "@ds/components/Modal";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export default function Modal({ open, onClose, title, children }: ModalProps) {
  return (
    <DSModal open={open} onClose={onClose} title={title} size="md">
      {children}
    </DSModal>
  );
}
