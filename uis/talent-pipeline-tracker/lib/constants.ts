import type { Stage, Status } from "@/types";

export const STATUS_OPTIONS: { value: Status; label: string }[] = [
  { value: "received", label: "Recibida" },
  { value: "in_progress", label: "En proceso" },
  { value: "selected", label: "Seleccionada" },
  { value: "discarded", label: "Descartada" },
];

export const STAGE_OPTIONS: { value: Stage; label: string }[] = [
  { value: "pending", label: "Pendiente" },
  { value: "review", label: "En revisión" },
  { value: "personal_interview", label: "Entrevista personal" },
  { value: "technical_interview", label: "Entrevista técnica" },
  { value: "offer_presented", label: "Oferta presentada" },
];

export const STATUS_LABELS: Record<Status, string> = Object.fromEntries(
  STATUS_OPTIONS.map(({ value, label }) => [value, label]),
) as Record<Status, string>;

export const STAGE_LABELS: Record<Stage, string> = Object.fromEntries(
  STAGE_OPTIONS.map(({ value, label }) => [value, label]),
) as Record<Stage, string>;

export type BadgeStyle = {
  surface: string;
  dot: string;
  pulseDot?: boolean;
};

export const STATUS_BADGE_STYLES: Record<Status, BadgeStyle> = {
  received: {
    surface: "bg-sky-50 text-sky-900 ring-1 ring-inset ring-sky-200/80",
    dot: "bg-sky-600",
  },
  in_progress: {
    surface: "bg-amber-50 text-amber-900 ring-1 ring-inset ring-amber-200/80",
    dot: "bg-amber-500",
    pulseDot: true,
  },
  selected: {
    surface: "bg-emerald-50 text-emerald-900 ring-1 ring-inset ring-emerald-200/80",
    dot: "bg-emerald-600",
  },
  discarded: {
    surface: "bg-rose-50 text-rose-900 ring-1 ring-inset ring-rose-200/80",
    dot: "bg-rose-600",
  },
};

export const STAGE_BADGE_STYLES: Record<Stage, BadgeStyle> = {
  pending: {
    surface: "bg-stone-50 text-stone-800 ring-1 ring-inset ring-stone-200/80",
    dot: "bg-stone-400",
  },
  review: {
    surface: "bg-stone-50 text-stone-800 ring-1 ring-inset ring-stone-200/80",
    dot: "bg-stone-500",
  },
  personal_interview: {
    surface: "bg-stone-50 text-stone-800 ring-1 ring-inset ring-stone-200/80",
    dot: "bg-stone-500",
  },
  technical_interview: {
    surface: "bg-stone-50 text-stone-800 ring-1 ring-inset ring-stone-200/80",
    dot: "bg-stone-600",
  },
  offer_presented: {
    surface: "bg-orange-50 text-orange-900 ring-1 ring-inset ring-orange-200/80",
    dot: "bg-orange-500",
  },
};

export const COMPANY_NAME = "Brasaland";
export const DEPARTMENT_NAME = "People & Talent";
