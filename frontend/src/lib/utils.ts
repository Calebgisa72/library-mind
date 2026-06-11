import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names with conflict resolution. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a 0–1 cosine similarity as a percentage string. */
export function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/** Format a USD amount with sensible precision. */
export function formatUsd(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount < 1 ? 4 : 2,
    maximumFractionDigits: 4,
  }).format(amount);
}

/** Title-case a single token (e.g. enum value) for display. */
export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** A short relative-time string for timestamps (e.g. "2m ago"). */
export function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}
