"use client";

import { MessagesSquare, Plus, SendHorizontal, Trash2, BookMarked } from "lucide-react";
import * as React from "react";

import { SourcesList } from "@/components/shared/sources";
import { ErrorAlert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Textarea } from "@/components/ui/input";
import { LoadingDots } from "@/components/ui/spinner";
import { useChat } from "@/lib/hooks";
import { useConversations, newMessage } from "@/lib/conversations";
import { chatRequestSchema } from "@/lib/schemas";
import { cn, timeAgo } from "@/lib/utils";

export default function ChatPage() {
  const convo = useConversations();
  const chat = useChat();
  const [draft, setDraft] = React.useState("");
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const messages = convo.active?.messages ?? [];

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, chat.isPending]);

  async function send() {
    const text = draft.trim();
    if (!text || chat.isPending) return;

    let conversationId = convo.activeId;
    if (!conversationId) conversationId = convo.createConversation();

    const parsed = chatRequestSchema.safeParse({ conversation_id: conversationId, message: text });
    if (!parsed.success) return;

    const isFirst = (convo.active?.messages.length ?? 0) === 0;
    convo.appendMessage(conversationId, newMessage("user", text), isFirst);
    setDraft("");

    chat.mutate(parsed.data, {
      onSuccess: (res) => {
        convo.appendMessage(conversationId!, newMessage("assistant", res.reply, res.sources));
      },
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary ring-1 ring-inset ring-primary/20">
            <MessagesSquare className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              A multi-turn conversation with the AI librarian. History is preserved per conversation
              and each reply retrieves fresh catalogue context.
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => convo.createConversation()}>
          <Plus className="h-4 w-4" /> New chat
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        {/* History */}
        <aside className="flex max-h-[60vh] flex-col gap-1.5 overflow-y-auto rounded-lg border border-border bg-card p-2 lg:max-h-[68vh] scrollbar-thin">
          {convo.conversations.length === 0 ? (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground">
              No conversations yet.
            </p>
          ) : (
            convo.conversations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "group flex items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors",
                  c.id === convo.activeId
                    ? "bg-primary/12 text-primary"
                    : "hover:bg-accent",
                )}
              >
                <button
                  onClick={() => convo.setActiveId(c.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="block truncate font-medium">{c.title}</span>
                  <span className="block text-[11px] text-muted-foreground">
                    {c.messages.length} msg · {timeAgo(new Date(c.updatedAt))}
                  </span>
                </button>
                <button
                  aria-label="Delete conversation"
                  onClick={() => convo.deleteConversation(c.id)}
                  className="opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          )}
        </aside>

        {/* Thread */}
        <div className="flex max-h-[68vh] min-h-[420px] flex-col rounded-lg border border-border bg-card">
          <div ref={scrollRef} className="scrollbar-thin flex-1 space-y-4 overflow-y-auto p-4">
            {messages.length === 0 && !chat.isPending ? (
              <div className="flex h-full items-center justify-center">
                <EmptyState
                  icon={MessagesSquare}
                  title="Start the conversation"
                  description="Ask the librarian for recommendations, comparisons, or help finding the right book."
                  className="border-0"
                />
              </div>
            ) : null}

            {messages.map((m) => (
              <div
                key={m.id}
                className={cn("flex animate-fade-in", m.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={cn(
                    "max-w-[80%] space-y-3 rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                    m.role === "user"
                      ? "rounded-br-sm bg-primary text-primary-foreground"
                      : "rounded-bl-sm bg-muted text-foreground",
                  )}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  {m.sources && m.sources.length > 0 ? (
                    <div className="rounded-lg bg-background/70 p-2.5">
                      <SourcesList sources={m.sources} />
                    </div>
                  ) : null}
                </div>
              </div>
            ))}

            {chat.isPending ? (
              <div className="flex justify-start animate-fade-in">
                <div className="rounded-2xl rounded-bl-sm bg-muted px-4 py-3">
                  <LoadingDots label="The librarian is thinking" />
                </div>
              </div>
            ) : null}
          </div>

          {chat.isError ? (
            <div className="px-4">
              <ErrorAlert error={chat.error} />
            </div>
          ) : null}

          <div className="border-t border-border p-3">
            <div className="flex items-end gap-2">
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Message the librarian…"
                rows={1}
                maxLength={4000}
                className="min-h-[44px] resize-none"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
              />
              <Button
                onClick={() => void send()}
                disabled={chat.isPending || draft.trim().length === 0}
                size="icon"
                aria-label="Send message"
                className="h-11 w-11"
              >
                <SendHorizontal className="h-4 w-4" />
              </Button>
            </div>
            <p className="mt-1.5 flex items-center gap-1 px-1 text-[11px] text-muted-foreground">
              <BookMarked className="h-3 w-3" />
              Enter to send · Shift + Enter for a new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
