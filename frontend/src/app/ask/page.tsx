"use client";

import { Sparkles, Send, Zap } from "lucide-react";
import * as React from "react";

import { SourcesList } from "@/components/shared/sources";
import { ErrorAlert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/input";
import { LoadingDots } from "@/components/ui/spinner";
import { useAsk } from "@/lib/hooks";
import { askRequestSchema } from "@/lib/schemas";

const EXAMPLES = [
  "What books do you recommend for someone new to philosophy?",
  "Which titles cover the history of computing?",
  "Do you have anything about resilience and overcoming adversity?",
];

export default function AskPage() {
  const [question, setQuestion] = React.useState("");
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const ask = useAsk();

  function submit(q: string) {
    const parsed = askRequestSchema.safeParse({ question: q });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Invalid question.");
      return;
    }
    setValidationError(null);
    ask.mutate(parsed.data);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Sparkles}
        title="Ask the Librarian"
        description="Get answers grounded strictly in the library catalogue. Every response cites the source books it drew from — no outside knowledge, no hallucinated titles."
      />

      <Card>
        <CardContent className="pt-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit(question);
            }}
            className="space-y-3"
          >
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about the catalogue…"
              maxLength={1000}
              rows={3}
              aria-label="Your question"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  submit(question);
                }
              }}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {question.length}/1000 · Press ⌘/Ctrl + Enter to send
              </span>
              <Button type="submit" disabled={ask.isPending}>
                {ask.isPending ? <LoadingDots /> : <Send className="h-4 w-4" />}
                {ask.isPending ? "" : "Ask"}
              </Button>
            </div>
            {validationError ? (
              <p className="text-sm text-destructive">{validationError}</p>
            ) : null}
          </form>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Examples:</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => {
                  setQuestion(ex);
                  submit(ex);
                }}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-foreground"
              >
                {ex}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {ask.isError ? <ErrorAlert error={ask.error} /> : null}

      {ask.isSuccess ? (
        <Card className="animate-fade-in">
          <CardContent className="space-y-5 pt-6">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                <Sparkles className="h-4 w-4 text-primary" />
                Answer
              </h2>
              {ask.data?.cached ? (
                <Badge tone="primary" title="Served from cache — no AI call was made">
                  <Zap className="h-3 w-3" /> Cached
                </Badge>
              ) : (
                <Badge tone="muted">Fresh</Badge>
              )}
            </div>
            <p className="whitespace-pre-wrap leading-relaxed text-foreground">
              {ask.data?.answer}
            </p>
            <div className="border-t border-border pt-4">
              <SourcesList sources={ask.data?.sources ?? []} />
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!ask.isSuccess && !ask.isError && !ask.isPending ? (
        <EmptyState
          icon={Sparkles}
          title="Ask anything about the collection"
          description="The librarian answers only from books in the catalogue and always shows its sources."
        />
      ) : null}
    </div>
  );
}
