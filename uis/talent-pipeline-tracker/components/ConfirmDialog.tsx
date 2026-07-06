"use client";

import { useEffect, useId, useRef } from "react";

/**
 * Reusable confirmation dialog for destructive actions (delete, remove).
 * All destructive UI flows must use this component before calling the API.
 */
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  variant = "default",
  isLoading = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "default";
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    cancelRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isLoading) {
        onCancel();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, isLoading, onCancel]);

  if (!open) return null;

  const confirmButtonClass =
    variant === "danger"
      ? "bg-rose-600 text-white hover:bg-rose-500 disabled:bg-stone-200 disabled:text-stone-500"
      : "bg-orange-600 text-white hover:bg-orange-500 disabled:bg-stone-200 disabled:text-stone-500";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Cerrar diálogo"
        className="absolute inset-0 bg-stone-900/50"
        onClick={() => {
          if (!isLoading) onCancel();
        }}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-md rounded-xl border border-stone-200 bg-white p-6 shadow-xl"
      >
        <h2 id={titleId} className="text-lg font-semibold text-stone-900">
          {title}
        </h2>
        <p className="mt-2 text-sm text-stone-600">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            ref={cancelRef}
            type="button"
            disabled={isLoading}
            onClick={onCancel}
            className="rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:bg-stone-100 disabled:text-stone-500"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            disabled={isLoading}
            onClick={onConfirm}
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${confirmButtonClass}`}
          >
            {isLoading ? "Procesando..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
