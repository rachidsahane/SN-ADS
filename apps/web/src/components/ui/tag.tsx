import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

// Noms de classes écrits en entier : Tailwind ne retrouve pas ceux qu'on assemble avec une variable.
const TONES = {
  accent: "tag tag-accent",
  neutral: "tag tag-neutral",
  outline: "tag tag-outline",
} as const;

type TagProps = {
  tone?: keyof typeof TONES;
  className?: string;
  children: ReactNode;
  "data-testid"?: string;
};

/** Étiquette du prototype (`.tag`) : accent, neutre ou contour. */
export function Tag({ tone = "neutral", className, children, ...rest }: TagProps) {
  return (
    <span className={cn(TONES[tone], className)} {...rest}>
      {children}
    </span>
  );
}
