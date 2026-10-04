import * as React from "react";

import { cn } from "@/lib/utils";

/** Liste déroulante native, mêmes classes que `Input` (D-070 : pas de Radix). */
const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select ref={ref} className={cn("input", className)} {...props}>
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export { Select };
