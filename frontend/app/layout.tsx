import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LeadScout · AI agent team for outreach",
  description: "Three AI agents research a company, write a personalized email, and review it. Built with LangGraph and Claude.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
