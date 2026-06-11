import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} aria-hidden />;
}

export function LoadingDots({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground" role="status">
      <span className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-primary"
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        ))}
      </span>
      {label ? <span className="text-sm">{label}</span> : null}
    </span>
  );
}
