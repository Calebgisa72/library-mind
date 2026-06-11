"use client";

/**
 * TanStack Query hooks wrapping the typed API client.
 *
 * Mutations are used for the AI endpoints (they are user-triggered actions
 * with side effects / cost), while /health is a polling query suited to a
 * live admin dashboard.
 */
import { useMutation, useQuery } from "@tanstack/react-query";

import { api, type ApiError } from "./api";
import type {
  AskRequest,
  AskResponse,
  ChatRequest,
  ChatResponse,
  ClassifyTicketRequest,
  ReviewSummary,
  SearchBooksRequest,
  SearchBooksResponse,
  SummariseReviewsRequest,
  TicketClassification,
} from "./schemas";

export function useSearchBooks() {
  return useMutation<SearchBooksResponse, ApiError, SearchBooksRequest>({
    mutationFn: (body) => api.searchBooks(body),
  });
}

export function useAsk() {
  return useMutation<AskResponse, ApiError, AskRequest>({
    mutationFn: (body) => api.ask(body),
  });
}

export function useChat() {
  return useMutation<ChatResponse, ApiError, ChatRequest>({
    mutationFn: (body) => api.chat(body),
  });
}

export function useClassifyTicket() {
  return useMutation<TicketClassification, ApiError, ClassifyTicketRequest>({
    mutationFn: (body) => api.classifyTicket(body),
  });
}

export function useSummariseReviews() {
  return useMutation<ReviewSummary, ApiError, SummariseReviewsRequest>({
    mutationFn: (body) => api.summariseReviews(body),
  });
}

export function useHealth(options?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: options?.refetchInterval ?? 15_000,
    retry: 1,
  });
}
