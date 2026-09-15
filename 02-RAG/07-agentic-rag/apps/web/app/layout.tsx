import type { Metadata } from "next";

import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fieldnote — Agentic RAG",
  description: "Private knowledge, clear answers, verifiable citations.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body data-auth-disabled={process.env.AUTH_DISABLED === "true"}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
