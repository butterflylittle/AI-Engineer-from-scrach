import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost" | "danger";
  size?: "default" | "sm" | "icon";
};

export function Button({ className, variant = "default", size = "default", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ink)]/30 disabled:pointer-events-none disabled:opacity-50",
        variant === "default" && "bg-[var(--ink)] text-white shadow-[0_7px_20px_rgba(26,28,25,.16)] hover:-translate-y-px hover:bg-black",
        variant === "outline" && "border border-[var(--line)] bg-white/70 text-[var(--ink)] hover:border-[var(--ink)]",
        variant === "ghost" && "text-[var(--muted)] hover:bg-black/5 hover:text-[var(--ink)]",
        variant === "danger" && "bg-red-50 text-red-700 hover:bg-red-100",
        size === "default" && "h-11 px-5",
        size === "sm" && "h-9 px-4 text-xs",
        size === "icon" && "size-10",
        className,
      )}
      {...props}
    />
  );
}
