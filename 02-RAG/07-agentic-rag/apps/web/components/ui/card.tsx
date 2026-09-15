import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-3xl border border-[var(--line)] bg-white/74 shadow-[0_20px_70px_rgba(26,28,25,.06)] backdrop-blur", className)} {...props} />;
}
