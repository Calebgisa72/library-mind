import { AlertTriangle, Info, WifiOff } from "lucide-react";

import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ErrorAlertProps {
  error: unknown;
  className?: string;
}

/** Render a normalised, user-friendly error message. */
export function ErrorAlert({ error, className }: ErrorAlertProps) {
  const isNetwork = error instanceof ApiError && error.isNetwork;
  const message =
    error instanceof Error ? error.message : "Something went wrong. Please try again.";

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive animate-fade-in",
        className,
      )}
    >
      {isNetwork ? (
        <WifiOff className="mt-0.5 h-5 w-5 shrink-0" />
      ) : (
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
      )}
      <div>
        <p className="font-medium">{isNetwork ? "Connection problem" : "Request failed"}</p>
        <p className="mt-0.5 text-destructive/90">{message}</p>
      </div>
    </div>
  );
}

export function InfoNote({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-md border border-border bg-muted/50 p-4 text-sm text-muted-foreground",
        className,
      )}
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      <div>{children}</div>
    </div>
  );
}
