import * as React from "react";

import { cn } from "@/lib/utils";

type Tone =
  | "default"
  | "primary"
  | "muted"
  | "success"
  | "warning"
  | "destructive"
  | "outline";

const tones: Record<Tone, string> = {
  default: "bg-secondary text-secondary-foreground",
  primary: "bg-primary/12 text-primary ring-1 ring-inset ring-primary/25",
  muted: "bg-muted text-muted-foreground",
  success: "bg-success/12 text-success ring-1 ring-inset ring-success/25",
  warning: "bg-warning/15 text-warning-foreground ring-1 ring-inset ring-warning/30",
  destructive: "bg-destructive/12 text-destructive ring-1 ring-inset ring-destructive/25",
  outline: "border border-border text-foreground",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
