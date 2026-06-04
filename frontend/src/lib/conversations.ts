"use client";

/**
 * Client-side conversation store for the chat feature.
 *
 * The backend keeps chat history per `conversation_id` but exposes no list or
 * fetch endpoint, so the client owns the index of conversations and the local
 * transcript. Persistence is localStorage; everything is keyed by a generated
 * UUID that we send as `conversation_id`.
 */
import { useCallback, useEffect, useState } from "react";
import { v4 as uuidv4 } from "uuid";

import type { SourceBook } from "./schemas";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceBook[];
  createdAt: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = "librarymind.conversations.v1";

function read(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Conversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(conversations: Conversation[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

function deriveTitle(message: string): string {
  const trimmed = message.trim().replace(/\s+/g, " ");
  return trimmed.length > 42 ? `${trimmed.slice(0, 42)}…` : trimmed || "New conversation";
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = read();
    setConversations(stored);
    setActiveId(stored[0]?.id ?? null);
    setHydrated(true);
  }, []);

  const persist = useCallback((next: Conversation[]) => {
    setConversations(next);
    write(next);
  }, []);

  const createConversation = useCallback((): string => {
    const id = uuidv4();
    const now = Date.now();
    const conversation: Conversation = {
      id,
      title: "New conversation",
      messages: [],
      createdAt: now,
      updatedAt: now,
    };
    setConversations((prev) => {
      const next = [conversation, ...prev];
      write(next);
      return next;
    });
    setActiveId(id);
    return id;
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        write(next);
        setActiveId((current) => (current === id ? (next[0]?.id ?? null) : current));
        return next;
      });
    },
    [],
  );

  const renameConversation = useCallback((id: string, title: string) => {
    setConversations((prev) => {
      const next = prev.map((c) =>
        c.id === id ? { ...c, title: title.trim() || c.title } : c,
      );
      write(next);
      return next;
    });
  }, []);

  const appendMessage = useCallback(
    (conversationId: string, message: ChatMessage, isFirstUserMessage = false) => {
      setConversations((prev) => {
        const next = prev.map((c) => {
          if (c.id !== conversationId) return c;
          const title =
            isFirstUserMessage && c.messages.length === 0
              ? deriveTitle(message.content)
              : c.title;
          return {
            ...c,
            title,
            messages: [...c.messages, message],
            updatedAt: Date.now(),
          };
        });
        write(next);
        return next;
      });
    },
    [],
  );

  const clearAll = useCallback(() => {
    persist([]);
    setActiveId(null);
  }, [persist]);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  return {
    hydrated,
    conversations,
    active,
    activeId,
    setActiveId,
    createConversation,
    deleteConversation,
    renameConversation,
    appendMessage,
    clearAll,
  };
}

export function newMessage(
  role: ChatMessage["role"],
  content: string,
  sources?: SourceBook[],
): ChatMessage {
  return { id: uuidv4(), role, content, sources, createdAt: Date.now() };
}
