"use client";

import { Menu, X } from "lucide-react";
import * as React from "react";

import { HealthPill } from "./health-pill";
import { Logo } from "./logo";
import { SidebarNav } from "./sidebar-nav";
import { ThemeToggle } from "./theme-toggle";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = React.useState(false);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[280px_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-border bg-card/60 backdrop-blur lg:flex">
        <div className="flex h-16 items-center border-b border-border px-5">
          <Logo />
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto px-3 py-4">
          <SidebarNav />
        </div>
        <div className="border-t border-border p-3">
          <HealthPill />
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="flex flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur lg:hidden">
          <div className="flex items-center gap-2">
            <button
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-md border border-border hover:bg-accent"
            >
              <Menu className="h-5 w-5" />
            </button>
            <Logo showText={false} />
            <span className="text-base font-semibold tracking-tight">LibraryMind</span>
          </div>
          <ThemeToggle />
        </header>

        {/* Desktop header strip */}
        <header className="sticky top-0 z-20 hidden h-16 items-center justify-end gap-3 border-b border-border bg-background/70 px-6 backdrop-blur lg:flex">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            API docs ↗
          </a>
          <span className="h-5 w-px bg-border" />
          <ThemeToggle />
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-foreground/40 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div
            className={cn(
              "absolute left-0 top-0 flex h-full w-[280px] flex-col border-r border-border bg-card",
              "animate-fade-in",
            )}
          >
            <div className="flex h-16 items-center justify-between border-b border-border px-5">
              <Logo />
              <button
                aria-label="Close navigation"
                onClick={() => setMobileOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="scrollbar-thin flex-1 overflow-y-auto px-3 py-4">
              <SidebarNav onNavigate={() => setMobileOpen(false)} />
            </div>
            <div className="border-t border-border p-3">
              <HealthPill />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
