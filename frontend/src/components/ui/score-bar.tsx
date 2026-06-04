import { formatScore } from "@/lib/utils";
import { cn } from "@/lib/utils";

/** A compact relevance meter for a 0–1 cosine similarity score. */
export function ScoreBar({ score, className }: { score: number; className?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  return (
    <div className={cn("flex items-center gap-2", className)} title={`Relevance ${pct}%`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-xs font-medium text-muted-foreground">
        {formatScore(score)}
      </span>
    </div>
  );
}
