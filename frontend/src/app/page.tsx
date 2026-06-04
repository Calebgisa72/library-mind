"use client";

import Link from "next/link";
import { ArrowRight, DollarSign, Hash, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useHealth } from "@/lib/hooks";
import { NAV_ITEMS } from "@/lib/nav";
import { cn, formatUsd } from "@/lib/utils";

export default function DashboardPage() {
  const { data, isError } = useHealth();
  const features = NAV_ITEMS.filter((i) => i.href !== "/" && i.href !== "/health");

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-2xl border border-border bg-card p-8 shadow-soft">
        <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-primary/10 blur-3xl" aria-hidden />
        <div className="relative max-w-2xl">
          <Badge tone="primary" className="mb-4">
            <Sparkles className="h-3 w-3" /> AI library assistant
          </Badge>
          <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            LibraryMind, in one place.
          </h1>
          <p className="mt-3 text-muted-foreground">
            Semantic catalogue search, grounded Q&amp;A, a multi-turn librarian chatbot, support-ticket
            triage, and review summarisation — all powered by a resilient multi-provider AI backend.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/search"
              className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground shadow-glow transition-colors hover:bg-primary/90"
            >
              Start searching <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/chat"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-input px-5 text-sm font-medium transition-colors hover:bg-accent"
            >
              Chat with the librarian
            </Link>
          </div>
        </div>
      </section>

      {/* Live status strip */}
      <section className="grid gap-4 sm:grid-cols-3">
        <StatusCard
          label="System status"
          value={
            isError ? (
              <Badge tone="destructive">API offline</Badge>
            ) : data ? (
              <Badge tone={data.status === "ok" ? "success" : "warning"}>
                {data.status === "ok" ? "Operational" : "Degraded"}
              </Badge>
            ) : (
              <Spinner />
            )
          }
          hint={data ? `v${data.version} · cache ${data.cache}` : "Connecting to backend…"}
        />
        <StatusCard
          icon={<DollarSign className="h-4 w-4" />}
          label="Spend today"
          value={
            data ? (
              <span className="text-xl font-semibold tabular-nums">{formatUsd(data.daily_cost_usd)}</span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )
          }
          hint={data?.daily_budget_usd ? `of ${formatUsd(data.daily_budget_usd)} budget` : "No budget cap"}
        />
        <StatusCard
          icon={<Hash className="h-4 w-4" />}
          label="Requests today"
          value={
            data ? (
              <span className="text-xl font-semibold tabular-nums">
                {data.request_count_today.toLocaleString()}
              </span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )
          }
          hint="Across all endpoints"
        />
      </section>

      {/* Feature grid */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Capabilities</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className="group">
                <Card className="h-full transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-glow">
                  <CardContent className="space-y-3 pt-6">
                    <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/12 text-primary ring-1 ring-inset ring-primary/20">
                      <Icon className="h-5 w-5" />
                    </span>
                    <div>
                      <h3 className="flex items-center gap-1 font-semibold">
                        {item.label}
                        <ArrowRight className="h-4 w-4 -translate-x-1 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
                      </h3>
                      <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function StatusCard({
  icon,
  label,
  value,
  hint,
}: {
  icon?: React.ReactNode;
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className={cn("space-y-2 pt-6")}>
        <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {icon ? <span className="text-primary">{icon}</span> : null}
          {label}
        </p>
        <div className="flex min-h-[1.75rem] items-center">{value}</div>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
