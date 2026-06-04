import { Library } from "lucide-react";

import { cn } from "@/lib/utils";

export function Logo({ className, showText = true }: { className?: string; showText?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-glow">
        <Library className="h-5 w-5" />
      </span>
      {showText ? (
        <span className="flex flex-col leading-none">
          <span className="text-base font-semibold tracking-tight">LibraryMind</span>
          <span className="text-[11px] font-medium text-muted-foreground">AI library assistant</span>
        </span>
      ) : null}
    </div>
  );
}
