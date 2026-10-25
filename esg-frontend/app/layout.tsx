import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ESG AI Engine",
  description: "SLM-powered ESG reporting copilot — BRSR, SDGs, GHG analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
