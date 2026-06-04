"use client";

import { BookOpen, CalendarDays, Search, User } from "lucide-react";
import * as React from "react";

import { ErrorAlert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { ScoreBar } from "@/components/ui/score-bar";
import { Spinner } from "@/components/ui/spinner";
import { useSearchBooks } from "@/lib/hooks";
import { searchBooksRequestSchema } from "@/lib/schemas";

const EXAMPLES = [
  "space exploration and the future of humanity",
  "coming-of-age stories set in small towns",
  "books about building good habits",
  "epic fantasy with morally grey characters",
];

export default function SearchPage() {
  const [query, setQuery] = React.useState("");
  const [limit, setLimit] = React.useState(10);
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const search = useSearchBooks();

  function runSearch(q: string) {
    const parsed = searchBooksRequestSchema.safeParse({ query: q, limit });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Invalid query.");
      return;
    }
    setValidationError(null);
    search.mutate(parsed.data);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    runSearch(query);
  }

  const results = search.data?.results ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        icon={BookOpen}
        title="Catalogue Search"
        description="Search the library catalogue by meaning, not keywords. Results are ranked by semantic (cosine) similarity to your phrase."
      />

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Describe what you're looking for…"
                  className="pl-9"
                  maxLength={500}
                  aria-label="Search query"
                />
              </div>
              <Button type="submit" disabled={search.isPending} className="sm:w-32">
                {search.isPending ? <Spinner /> : <Search className="h-4 w-4" />}
                {search.isPending ? "Searching" : "Search"}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-3 text-sm text-muted-foreground">
                <span className="whitespace-nowrap">Max results</span>
                <input
                  type="range"
                  min={1}
                  max={50}
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value))}
                  className="h-1.5 w-40 cursor-pointer accent-primary"
                />
                <span className="w-6 tabular-nums font-medium text-foreground">{limit}</span>
              </label>
            </div>

            {validationError ? (
              <p className="text-sm text-destructive">{validationError}</p>
            ) : null}
          </form>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Try:</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => {
                  setQuery(ex);
                  runSearch(ex);
                }}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-foreground"
              >
                {ex}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {search.isError ? <ErrorAlert error={search.error} /> : null}

      {search.isSuccess ? (
        results.length > 0 ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {results.length} {results.length === 1 ? "result" : "results"} for{" "}
              <span className="font-medium text-foreground">“{search.data?.query}”</span>
            </p>
            <div className="grid gap-3">
              {results.map((book, i) => (
                <Card key={book.id} className="animate-fade-in transition-colors hover:border-primary/30">
                  <CardContent className="flex items-start gap-4 py-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-sm font-semibold text-primary">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <h3 className="font-semibold leading-snug">{book.title}</h3>
                        <ScoreBar score={book.score} />
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                        <span className="inline-flex items-center gap-1">
                          <User className="h-3.5 w-3.5" />
                          {book.author}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <CalendarDays className="h-3.5 w-3.5" />
                          {book.year}
                        </span>
                        <Badge tone="primary">{book.genre}</Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState
            icon={Search}
            title="No matching books"
            description="Try rephrasing your query or describing the themes you're interested in."
          />
        )
      ) : null}

      {!search.isSuccess && !search.isError && !search.isPending ? (
        <EmptyState
          icon={BookOpen}
          title="Search the catalogue"
          description="Enter a natural-language phrase above to find semantically similar books."
        />
      ) : null}
    </div>
  );
}
