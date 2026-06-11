"use client";

import { Minus, Plus, Star, ThumbsDown, ThumbsUp, Tag, Wand2 } from "lucide-react";
import * as React from "react";

import { ErrorAlert } from "@/components/ui/alert";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useSummariseReviews } from "@/lib/hooks";
import { summariseReviewsRequestSchema, type ReviewSummary } from "@/lib/schemas";
import { cn, titleCase } from "@/lib/utils";

const SENTIMENT_TONE: Record<ReviewSummary["overall_sentiment"], BadgeProps["tone"]> = {
  positive: "success",
  neutral: "muted",
  negative: "destructive",
  mixed: "warning",
};

const SAMPLE = [
  "Absolutely gripping from the first page. The world-building is rich and the characters feel real. Couldn't put it down.",
  "The pacing dragged in the middle third and some side plots went nowhere, but the ending mostly redeemed it.",
  "Beautiful prose, but I found the protagonist hard to root for. Still, the themes of memory and loss stuck with me.",
];

export default function SummarisePage() {
  const [reviews, setReviews] = React.useState<string[]>(["", ""]);
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const summarise = useSummariseReviews();

  function update(index: number, value: string) {
    setReviews((prev) => prev.map((r, i) => (i === index ? value : r)));
  }
  function add() {
    setReviews((prev) => (prev.length >= 50 ? prev : [...prev, ""]));
  }
  function remove(index: number) {
    setReviews((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)));
  }

  function submit() {
    const cleaned = reviews.map((r) => r.trim()).filter((r) => r.length > 0);
    const parsed = summariseReviewsRequestSchema.safeParse({ reviews: cleaned });
    if (!parsed.success) {
      setValidationError(parsed.error.issues[0]?.message ?? "Invalid reviews.");
      return;
    }
    setValidationError(null);
    summarise.mutate(parsed.data);
  }

  const result = summarise.data;
  const filledCount = reviews.filter((r) => r.trim().length > 0).length;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Star}
        title="Summarise Reviews"
        description="Aggregate 1–50 reader reviews into a structured analysis: overall sentiment, an estimated rating, recurring themes, praise, criticism, and a recommendation."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="space-y-3 pt-6">
            <div className="space-y-3">
              {reviews.map((review, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="mt-2.5 w-5 shrink-0 text-center text-xs font-medium text-muted-foreground">
                    {i + 1}
                  </span>
                  <Textarea
                    value={review}
                    onChange={(e) => update(i, e.target.value)}
                    placeholder={`Review ${i + 1}…`}
                    rows={2}
                    maxLength={4000}
                    aria-label={`Review ${i + 1}`}
                  />
                  <button
                    type="button"
                    onClick={() => remove(i)}
                    disabled={reviews.length <= 1}
                    aria-label="Remove review"
                    className="mt-1.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-destructive disabled:opacity-40"
                  >
                    <Minus className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" onClick={add} disabled={reviews.length >= 50}>
                  <Plus className="h-4 w-4" /> Add review
                </Button>
                <button
                  type="button"
                  onClick={() => {
                    setReviews(SAMPLE);
                    setValidationError(null);
                  }}
                  className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                >
                  Load samples
                </button>
              </div>
              <span className="text-xs text-muted-foreground">{filledCount}/50 reviews</span>
            </div>

            {validationError ? (
              <p className="text-sm text-destructive">{validationError}</p>
            ) : null}

            <Button onClick={submit} disabled={summarise.isPending} className="w-full">
              {summarise.isPending ? <Spinner /> : <Wand2 className="h-4 w-4" />}
              {summarise.isPending ? "Summarising" : "Summarise reviews"}
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {summarise.isError ? <ErrorAlert error={summarise.error} /> : null}

          {result ? (
            <Card className="animate-fade-in">
              <CardContent className="space-y-5 pt-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <Stars rating={result.estimated_rating} />
                  <Badge tone={SENTIMENT_TONE[result.overall_sentiment]}>
                    {titleCase(result.overall_sentiment)}
                  </Badge>
                </div>

                <ListBlock
                  icon={<Tag className="h-4 w-4 text-primary" />}
                  title="Themes"
                  items={result.themes}
                  variant="badge"
                />
                <ListBlock
                  icon={<ThumbsUp className="h-4 w-4 text-success" />}
                  title="Praise"
                  items={result.praise}
                />
                <ListBlock
                  icon={<ThumbsDown className="h-4 w-4 text-destructive" />}
                  title="Criticism"
                  items={result.criticism}
                />

                <div className="rounded-lg bg-primary/8 p-4 ring-1 ring-inset ring-primary/15">
                  <p className="text-xs font-medium uppercase tracking-wide text-primary">
                    Recommendation
                  </p>
                  <p className="mt-1 text-sm leading-relaxed">{result.recommendation}</p>
                </div>
              </CardContent>
            </Card>
          ) : !summarise.isError ? (
            <EmptyState
              icon={Star}
              title="Summary appears here"
              description="Add a few reviews and run the summariser to see aggregated insights."
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex">
        {[1, 2, 3, 4, 5].map((i) => {
          const fill = Math.max(0, Math.min(1, rating - (i - 1)));
          return (
            <span key={i} className="relative h-5 w-5">
              <Star className="absolute h-5 w-5 text-muted-foreground/30" />
              <span className="absolute overflow-hidden" style={{ width: `${fill * 100}%` }}>
                <Star className="h-5 w-5 fill-warning text-warning" />
              </span>
            </span>
          );
        })}
      </div>
      <span className="text-sm font-semibold tabular-nums">{rating.toFixed(1)}</span>
      <span className="text-xs text-muted-foreground">/ 5</span>
    </div>
  );
}

function ListBlock({
  icon,
  title,
  items,
  variant = "list",
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  variant?: "list" | "badge";
}) {
  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
        <span className="font-normal normal-case text-muted-foreground/70">({items.length})</span>
      </p>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None identified.</p>
      ) : variant === "badge" ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((item, i) => (
            <Badge key={i} tone="primary">
              {item}
            </Badge>
          ))}
        </div>
      ) : (
        <ul className="space-y-1">
          {items.map((item, i) => (
            <li key={i} className={cn("flex gap-2 text-sm")}>
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
              <span className="leading-relaxed">{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
