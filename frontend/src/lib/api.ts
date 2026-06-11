/**
 * Typed API client for the LibraryMind backend.
 *
 * Each method validates the response with the matching Zod schema so the rest
 * of the app can trust the shapes it receives. Errors are normalised into a
 * single {@link ApiError} type that carries an HTTP status and a friendly,
 * user-facing message derived from the backend's `{ detail }` envelope or
 * FastAPI's 422 validation payload.
 */
import axios, { AxiosError, type AxiosInstance } from "axios";
import { z } from "zod";

import {
  askRequestSchema,
  askResponseSchema,
  chatRequestSchema,
  chatResponseSchema,
  classifyTicketRequestSchema,
  healthResponseSchema,
  reviewSummarySchema,
  searchBooksRequestSchema,
  searchBooksResponseSchema,
  summariseReviewsRequestSchema,
  ticketClassificationSchema,
  type AskRequest,
  type AskResponse,
  type ChatRequest,
  type ChatResponse,
  type ClassifyTicketRequest,
  type HealthResponse,
  type ReviewSummary,
  type SearchBooksRequest,
  type SearchBooksResponse,
  type SummariseReviewsRequest,
  type TicketClassification,
} from "./schemas";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

/** Normalised error surfaced throughout the UI. */
export class ApiError extends Error {
  readonly status: number;
  readonly isNetwork: boolean;
  readonly isRateLimit: boolean;
  readonly isUnavailable: boolean;

  constructor(message: string, status: number, isNetwork = false) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.isNetwork = isNetwork;
    this.isRateLimit = status === 429;
    this.isUnavailable = status === 503;
  }
}

const fastApiValidationSchema = z.object({
  detail: z.array(
    z.object({
      loc: z.array(z.union([z.string(), z.number()])).optional(),
      msg: z.string(),
      type: z.string().optional(),
    }),
  ),
});

const detailSchema = z.object({ detail: z.string() });

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    if (!axiosError.response) {
      return new ApiError(
        "Cannot reach the LibraryMind API. Is the backend running on " +
          `${API_BASE_URL}?`,
        0,
        true,
      );
    }
    const { status, data } = axiosError.response;

    const validation = fastApiValidationSchema.safeParse(data);
    if (validation.success) {
      const first = validation.data.detail[0];
      const field = first?.loc?.filter((l) => l !== "body").join(".") ?? "input";
      return new ApiError(`Validation error on ${field}: ${first?.msg ?? "invalid input"}`, status);
    }

    const detail = detailSchema.safeParse(data);
    if (detail.success) return new ApiError(detail.data.detail, status);

    if (status === 429) return new ApiError("Rate limit exceeded. Please slow down.", status);
    if (status === 503) return new ApiError("The AI provider is temporarily unavailable.", status);
    return new ApiError(`Request failed with status ${status}.`, status);
  }
  if (error instanceof Error) return new ApiError(error.message, 0);
  return new ApiError("An unexpected error occurred.", 0);
}

const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

async function post<TReq, TRes>(
  path: string,
  body: TReq,
  // Allow schemas whose *input* type differs from the output (e.g. fields with
  // `.default(...)` are optional on input but present on output).
  reqSchema: z.ZodType<TReq, z.ZodTypeDef, any>,
  resSchema: z.ZodType<TRes, z.ZodTypeDef, any>,
): Promise<TRes> {
  const parsedBody = reqSchema.parse(body);
  try {
    const { data } = await http.post(path, parsedBody);
    return resSchema.parse(data);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ApiError("The API returned an unexpected response shape.", 0);
    }
    throw toApiError(error);
  }
}

export const api = {
  searchBooks(body: SearchBooksRequest): Promise<SearchBooksResponse> {
    return post("/search/books", body, searchBooksRequestSchema, searchBooksResponseSchema);
  },
  ask(body: AskRequest): Promise<AskResponse> {
    return post("/search/ask", body, askRequestSchema, askResponseSchema);
  },
  chat(body: ChatRequest): Promise<ChatResponse> {
    return post("/chat", body, chatRequestSchema, chatResponseSchema);
  },
  classifyTicket(body: ClassifyTicketRequest): Promise<TicketClassification> {
    return post(
      "/classify/ticket",
      body,
      classifyTicketRequestSchema,
      ticketClassificationSchema,
    );
  },
  summariseReviews(body: SummariseReviewsRequest): Promise<ReviewSummary> {
    return post(
      "/summarise/reviews",
      body,
      summariseReviewsRequestSchema,
      reviewSummarySchema,
    );
  },
  async health(): Promise<HealthResponse> {
    try {
      const { data } = await http.get("/health");
      return healthResponseSchema.parse(data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new ApiError("The API returned an unexpected response shape.", 0);
      }
      throw toApiError(error);
    }
  },
};
