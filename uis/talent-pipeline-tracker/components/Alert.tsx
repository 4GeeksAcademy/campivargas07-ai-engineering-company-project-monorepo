type AlertVariant = "error" | "success" | "info";

const variantStyles: Record<AlertVariant, string> = {
  error: "border-rose-200 bg-rose-50 text-rose-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  info: "border-sky-200 bg-sky-50 text-sky-800",
};

export default function Alert({
  variant = "info",
  title,
  message,
  onRetry,
}: {
  variant?: AlertVariant;
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className={`rounded-xl border px-4 py-3 ${variantStyles[variant]}`}
      role="alert"
    >
      {title && <p className="font-semibold">{title}</p>}
      <p className="text-sm">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className={`mt-3 rounded-lg bg-white px-3 py-1.5 text-sm font-medium shadow-sm transition hover:bg-stone-50 ${
            variant === "error"
              ? "text-rose-900"
              : variant === "success"
                ? "text-emerald-900"
                : "text-sky-900"
          }`}
        >
          Reintentar
        </button>
      )}
    </div>
  );
}
