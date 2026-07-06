import PillBadge from "@/components/PillBadge";
import { STATUS_BADGE_STYLES, STATUS_LABELS } from "@/lib/constants";
import type { Status } from "@/types";

export default function StatusBadge({ status }: { status: Status }) {
  return (
    <PillBadge label={STATUS_LABELS[status]} style={STATUS_BADGE_STYLES[status]} />
  );
}
