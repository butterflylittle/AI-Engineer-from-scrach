import * as React from "react";

import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-12 w-full rounded-xl border border-[var(--line)] bg-white/80 px-4 text-sm text-[var(--ink)] outline-none transition placeholder:text-[var(--muted)]/65 focus:border-[var(--ink)] focus:ring-4 focus:ring-black/5",
        className,
      )}
      {...props}
    />
  );
}
