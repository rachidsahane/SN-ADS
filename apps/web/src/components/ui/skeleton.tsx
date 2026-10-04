import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/** Bloc gris qui pulse : réserve la place du contenu pendant le chargement. */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div aria-hidden="true" className={cn("skeleton", className)} style={style} />;
}
