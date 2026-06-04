"use client";

import Link from "next/link";

import { useHealth } from "@/lib/hooks";
import { cn } from "@/lib/utils";

/** A compact live status indicator shown in the sidebar footer. */
export function HealthPill() {
  const { data, isError, isLoading } = useHealth({ refetchInterval: 20_000 });

  const state = isLoading
    ? { label: "Checking…", color: "bg-muted-foreground", pulse: true }
    : isError
      ? { label: "API offline", color: "bg-destructive", pulse: false }
      : data?.status === "ok"
        ? { label: "All systems go", color: "bg-success", pulse: true }
        : { label: "Degraded", color: "bg-warning", pulse: true };

  return (
    <Link
      href="/health"
      className="flex items-center gap-2.5 rounded-md border border-border bg-card px-3 py-2 text-xs transition-colors hover:bg-accent"
    >
      <span className="relative flex h-2.5 w-2.5">
        {state.pulse ? (
          <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", state.color)} />
        ) : null}
        <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", state.color)} />
      </span>
      <span className="font-medium text-foreground">{state.label}</span>
      {data ? <span className="ml-auto text-muted-foreground">v{data.version}</span> : null}
    </Link>
  );
}
