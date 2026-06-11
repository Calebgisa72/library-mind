import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { AppShell } from "@/components/layout/app-shell";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: {
    default: "LibraryMind — AI Library Assistant",
    template: "%s · LibraryMind",
  },
  description:
    "AI-powered intelligent library assistant: semantic catalogue search, grounded Q&A, a multi-turn librarian chatbot, ticket triage, and review summarisation.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#141210" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="font-sans">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
