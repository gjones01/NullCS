import { AlertTriangle, Eye, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

type RiskBadgeProps = {
  band?: string | null;
  className?: string;
};

const styles: Record<string, { label: string; icon: typeof AlertTriangle; tone: string }> = {
  high_priority: {
    label: "High Priority",
    icon: AlertTriangle,
    tone: "border-rose-500/30 bg-rose-500/12 text-rose-200",
  },
  review: {
    label: "Review",
    icon: Eye,
    tone: "border-amber-500/30 bg-amber-500/12 text-amber-100",
  },
  low: {
    label: "Low",
    icon: ShieldCheck,
    tone: "border-emerald-500/30 bg-emerald-500/12 text-emerald-100",
  },
  unknown: {
    label: "Unknown",
    icon: ShieldCheck,
    tone: "border-zinc-500/30 bg-zinc-500/10 text-zinc-200",
  },
};

export function RiskBadge({ band, className }: RiskBadgeProps) {
  const config = styles[String(band || "").toLowerCase()] || styles.unknown;
  const Icon = config.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[0.72rem] uppercase tracking-[0.2em]",
        config.tone,
        className
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {config.label}
    </span>
  );
}
