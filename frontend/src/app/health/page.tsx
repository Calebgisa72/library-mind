"use client";

import {
  Activity,
  CheckCircle2,
  Database,
  DollarSign,
  Hash,
  RefreshCw,
  Server,
  XCircle,
} from "lucide-react";

import { ErrorAlert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { useHealth } from "@/lib/hooks";
import { cn, formatUsd, titleCase } from "@/lib/utils";

export default function HealthPage() {
  const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useHealth();

  const budgetPct =
    data && data.daily_budget_usd
      ? Math.min(100, (data.daily_cost_usd / data.daily_budget_usd) * 100)
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Activity}
        title="System Health"
        description="Live operational status — provider configuration, cache connectivity, today's spend, and request volume. This view never triggers a paid AI call."
        actions={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? <Spinner /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
        }
      />

      {isError ? <ErrorAlert error={error} /> : null}

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Loading health…
        </div>
      ) : null}

      {data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={<Activity className="h-4 w-4" />}
              label="Status"
              value={
                <Badge tone={data.status === "ok" ? "success" : "warning"}>
                  {data.status === "ok" ? "Operational" : "Degraded"}
                </Badge>
              }
              hint={`Version ${data.version}`}
            />
            <StatCard
              icon={<Database className="h-4 w-4" />}
              label="Cache (Redis)"
              value={
                <Badge tone={data.cache === "connected" ? "success" : "destructive"}>
                  {titleCase(data.cache)}
                </Badge>
              }
              hint={data.cache === "connected" ? "Responses can be cached" : "Caching unavailable"}
            />
            <StatCard
              icon={<DollarSign className="h-4 w-4" />}
              label="Spend today"
              value={<span className="text-2xl font-semibold tabular-nums">{formatUsd(data.daily_cost_usd)}</span>}
              hint={data.daily_budget_usd ? `of ${formatUsd(data.daily_budget_usd)} budget` : "No budget cap set"}
            />
            <StatCard
              icon={<Hash className="h-4 w-4" />}
              label="Requests today"
              value={<span className="text-2xl font-semibold tabular-nums">{data.request_count_today.toLocaleString()}</span>}
              hint="Across all endpoints"
            />
          </div>

          {budgetPct !== null ? (
            <Card>
              <CardContent className="space-y-2 pt-6">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">Daily budget usage</span>
                  <span className="tabular-nums text-muted-foreground">
                    {formatUsd(data.daily_cost_usd)} / {formatUsd(data.daily_budget_usd!)}
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      budgetPct >= 90 ? "bg-destructive" : budgetPct >= 70 ? "bg-warning" : "bg-primary",
                    )}
                    style={{ width: `${Math.max(budgetPct, 1.5)}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{budgetPct.toFixed(1)}% of today's cap used</p>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardContent className="pt-6">
              <h2 className="flex items-center gap-2 text-sm font-medium">
                <Server className="h-4 w-4 text-primary" />
                AI Providers
              </h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {Object.entries(data.providers).map(([name, status]) => {
                  const configured = status === "configured";
                  return (
                    <div
                      key={name}
                      className="flex items-center justify-between rounded-md border border-border bg-background/50 px-4 py-3"
                    >
                      <span className="font-medium capitalize">{name}</span>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 text-sm",
                          configured ? "text-success" : "text-muted-foreground",
                        )}
                      >
                        {configured ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <XCircle className="h-4 w-4" />
                        )}
                        {configured ? "Configured" : "Not configured"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <p className="text-center text-xs text-muted-foreground">
            Auto-refreshes every 15s · Last updated {new Date(dataUpdatedAt).toLocaleTimeString()}
          </p>
        </>
      ) : null}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="space-y-2 pt-6">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <span className="text-primary">{icon}</span>
          {label}
        </div>
        <div className="flex min-h-[2rem] items-center">{value}</div>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
