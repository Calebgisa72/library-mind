"use client";

import { Building2, Tags, Wand2 } from "lucide-react";
import * as React from "react";

import { ErrorAlert } from "@/components/ui/alert";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useClassifyTicket } from "@/lib/hooks";
import { classifyTicketRequestSchema, type TicketClassification } from "@/lib/schemas";
import { titleCase } from "@/lib/utils";

const PRIORITY_TONE: Record<TicketClassification["priority"], BadgeProps["tone"]> = {
  low: "muted",
  medium: "primary",
  high: "warning",
  urgent: "destructive",
};

const SENTIMENT_TONE: Record<TicketClassification["sentiment"], BadgeProps["tone"]> = {
  positive: "success",
  neutral: "muted",
  negative: "destructive",
};

const SAMPLE =
  "I've been trying to renew my borrowed books online for three days but the website keeps throwing an error at checkout. I'm going to be charged late fees through no fault of my own. This is really frustrating.";

export default function ClassifyPage() {
  const [text, setText] = React.useState("");
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const classify = useClassifyTicket();

  function submit(value: string) {
    const parsed = classifyTicketRequestSchema.safeParse({ text: value });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Invalid ticket text.");
      return;
    }
    setValidationError(null);
    classify.mutate(parsed.data);
  }

  const result = classify.data;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Tags}
        title="Classify Ticket"
        description="Turn a free-text support ticket into structured triage fields — category, priority, sentiment, the department it should route to, and a one-line summary."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="space-y-3 pt-6">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submit(text);
              }}
              className="space-y-3"
            >
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste the support ticket text here…"
                rows={9}
                maxLength={4000}
                aria-label="Ticket text"
              />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setText(SAMPLE);
                    submit(SAMPLE);
                  }}
                  className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                >
                  Use a sample ticket
                </button>
                <Button type="submit" disabled={classify.isPending}>
                  {classify.isPending ? <Spinner /> : <Wand2 className="h-4 w-4" />}
                  {classify.isPending ? "Classifying" : "Classify"}
                </Button>
              </div>
              {validationError ? (
                <p className="text-sm text-destructive">{validationError}</p>
              ) : null}
            </form>
          </CardContent>
        </Card>

        <div>
          {classify.isError ? <ErrorAlert error={classify.error} /> : null}

          {result ? (
            <Card className="animate-fade-in">
              <CardContent className="space-y-5 pt-6">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <Field label="Category">
                    <Badge tone="primary">{titleCase(result.category)}</Badge>
                  </Field>
                  <Field label="Priority">
                    <Badge tone={PRIORITY_TONE[result.priority]}>
                      {titleCase(result.priority)}
                    </Badge>
                  </Field>
                  <Field label="Sentiment">
                    <Badge tone={SENTIMENT_TONE[result.sentiment]}>
                      {titleCase(result.sentiment)}
                    </Badge>
                  </Field>
                </div>

                <Field label="Suggested department">
                  <span className="inline-flex items-center gap-1.5 text-sm font-medium">
                    <Building2 className="h-4 w-4 text-primary" />
                    {result.department}
                  </span>
                </Field>

                <Field label="Summary">
                  <p className="text-sm leading-relaxed text-foreground">{result.summary}</p>
                </Field>
              </CardContent>
            </Card>
          ) : !classify.isError ? (
            <EmptyState
              icon={Tags}
              title="Classification appears here"
              description="Paste a ticket and run the classifier to see structured triage output."
              className="h-full"
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <div>{children}</div>
    </div>
  );
}
