import { BookMarked } from "lucide-react";

import { ScoreBar } from "@/components/ui/score-bar";
import type { SourceBook } from "@/lib/schemas";

/** Renders the grounded source citations attached to RAG / chat answers. */
export function SourcesList({ sources }: { sources: SourceBook[] }) {
  if (sources.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <BookMarked className="h-3.5 w-3.5" />
        Sources ({sources.length})
      </p>
      <ul className="space-y-1.5">
        {sources.map((s, i) => (
          <li
            key={`${s.title}-${i}`}
            className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/60 px-3 py-2"
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{s.title}</span>
              <span className="block truncate text-xs text-muted-foreground">{s.author}</span>
            </span>
            <ScoreBar score={s.score} className="shrink-0" />
          </li>
        ))}
      </ul>
    </div>
  );
}
