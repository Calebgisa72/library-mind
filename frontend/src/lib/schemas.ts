/**
 * Zod schemas mirroring the LibraryMind FastAPI Pydantic models.
 *
 * Request schemas reuse the backend's length constraints so we can validate
 * client-side before a network round trip. Response schemas validate the wire
 * format at runtime, surfacing contract drift early rather than letting bad
 * data flow into the UI.
 *
 * Source of truth: app/schemas/*.py and app/services/{classifier,summariser}.py
 */
import { z } from "zod";

/* ----------------------------- Shared ---------------------------------- */

export const sourceBookSchema = z.object({
  title: z.string(),
  author: z.string(),
  score: z.number().min(0).max(1),
});
export type SourceBook = z.infer<typeof sourceBookSchema>;

/* --------------------------- Search /books ----------------------------- */

export const searchBooksRequestSchema = z.object({
  query: z
    .string()
    .trim()
    .min(3, "Enter at least 3 characters.")
    .max(500, "Query must be 500 characters or fewer."),
  limit: z.number().int().min(1).max(50).default(10),
});
export type SearchBooksRequest = z.infer<typeof searchBooksRequestSchema>;

export const bookHitSchema = z.object({
  id: z.string(),
  title: z.string(),
  author: z.string(),
  year: z.number().int(),
  genre: z.string(),
  score: z.number().min(0).max(1),
});
export type BookHit = z.infer<typeof bookHitSchema>;

export const searchBooksResponseSchema = z.object({
  query: z.string(),
  results: z.array(bookHitSchema),
});
export type SearchBooksResponse = z.infer<typeof searchBooksResponseSchema>;

/* ----------------------------- Search /ask ----------------------------- */

export const askRequestSchema = z.object({
  question: z
    .string()
    .trim()
    .min(5, "Ask a question of at least 5 characters.")
    .max(1000, "Question must be 1000 characters or fewer."),
});
export type AskRequest = z.infer<typeof askRequestSchema>;

export const askResponseSchema = z.object({
  answer: z.string(),
  sources: z.array(sourceBookSchema),
  cached: z.boolean(),
});
export type AskResponse = z.infer<typeof askResponseSchema>;

/* -------------------------------- Chat --------------------------------- */

export const chatRequestSchema = z.object({
  conversation_id: z.string().min(1).max(64),
  message: z
    .string()
    .trim()
    .min(1, "Type a message.")
    .max(4000, "Message must be 4000 characters or fewer."),
});
export type ChatRequest = z.infer<typeof chatRequestSchema>;

export const chatResponseSchema = z.object({
  conversation_id: z.string(),
  reply: z.string(),
  sources: z.array(sourceBookSchema),
});
export type ChatResponse = z.infer<typeof chatResponseSchema>;

/* ------------------------------ Classify ------------------------------- */

export const classifyTicketRequestSchema = z.object({
  text: z
    .string()
    .trim()
    .min(5, "Ticket text must be at least 5 characters.")
    .max(4000, "Ticket text must be 4000 characters or fewer."),
});
export type ClassifyTicketRequest = z.infer<typeof classifyTicketRequestSchema>;

export const ticketCategorySchema = z.enum([
  "account",
  "borrowing",
  "technical",
  "complaint",
  "suggestion",
  "general",
]);
export const ticketPrioritySchema = z.enum(["low", "medium", "high", "urgent"]);
export const sentimentSchema = z.enum(["positive", "neutral", "negative"]);

export const ticketClassificationSchema = z.object({
  category: ticketCategorySchema,
  priority: ticketPrioritySchema,
  sentiment: sentimentSchema,
  department: z.string(),
  summary: z.string(),
});
export type TicketClassification = z.infer<typeof ticketClassificationSchema>;

/* ------------------------------ Summarise ------------------------------ */

export const summariseReviewsRequestSchema = z.object({
  reviews: z
    .array(
      z
        .string()
        .trim()
        .min(5, "Each review must be at least 5 characters.")
        .max(4000, "Each review must be 4000 characters or fewer."),
    )
    .min(1, "Add at least one review.")
    .max(50, "A maximum of 50 reviews can be summarised at once."),
});
export type SummariseReviewsRequest = z.infer<typeof summariseReviewsRequestSchema>;

export const overallSentimentSchema = z.enum([
  "positive",
  "neutral",
  "negative",
  "mixed",
]);

export const reviewSummarySchema = z.object({
  overall_sentiment: overallSentimentSchema,
  estimated_rating: z.number().min(1).max(5),
  themes: z.array(z.string()).default([]),
  praise: z.array(z.string()).default([]),
  criticism: z.array(z.string()).default([]),
  recommendation: z.string(),
});
export type ReviewSummary = z.infer<typeof reviewSummarySchema>;

/* ------------------------------- Health -------------------------------- */

export const healthResponseSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  version: z.string(),
  providers: z.record(z.string()),
  cache: z.enum(["connected", "unavailable"]),
  daily_cost_usd: z.number(),
  daily_budget_usd: z.number().nullable(),
  request_count_today: z.number().int(),
});
export type HealthResponse = z.infer<typeof healthResponseSchema>;
