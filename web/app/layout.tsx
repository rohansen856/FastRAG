import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FastRAG - Voice-enabled multilingual RAG",
  description:
    "Ask questions by voice across six languages against a grounded, citation-validated retrieval pipeline.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
