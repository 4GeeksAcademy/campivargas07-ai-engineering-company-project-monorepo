import type { BadgeStyle } from "@/lib/constants";

export default function PillBadge({
  label,
  style,
}: {
  label: string;
  style: BadgeStyle;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shadow-sm ${style.surface}`}
    >
      <span
        className={`size-1.5 shrink-0 rounded-full ${style.dot} ${style.pulseDot ? "animate-pulse" : ""}`}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
