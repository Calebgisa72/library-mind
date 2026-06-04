import {
  Activity,
  BookOpen,
  LayoutDashboard,
  MessagesSquare,
  Sparkles,
  Tags,
  Star,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

/** Primary navigation — one entry per backend capability. */
export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    description: "Overview & system status",
    icon: LayoutDashboard,
  },
  {
    href: "/search",
    label: "Catalogue Search",
    description: "Semantic book search",
    icon: BookOpen,
  },
  {
    href: "/ask",
    label: "Ask the Librarian",
    description: "Grounded RAG answers",
    icon: Sparkles,
  },
  {
    href: "/chat",
    label: "Chat",
    description: "Multi-turn AI librarian",
    icon: MessagesSquare,
  },
  {
    href: "/classify",
    label: "Classify Ticket",
    description: "Triage support tickets",
    icon: Tags,
  },
  {
    href: "/summarise",
    label: "Summarise Reviews",
    description: "Aggregate reader reviews",
    icon: Star,
  },
  {
    href: "/health",
    label: "System Health",
    description: "Usage, spend & providers",
    icon: Activity,
  },
];
