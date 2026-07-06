import PillBadge from "@/components/PillBadge";
import { STAGE_BADGE_STYLES, STAGE_LABELS } from "@/lib/constants";
import type { Stage } from "@/types";

export default function StageBadge({ stage }: { stage: Stage }) {
  return (
    <PillBadge label={STAGE_LABELS[stage]} style={STAGE_BADGE_STYLES[stage]} />
  );
}
