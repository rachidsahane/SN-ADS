import * as React from "react";

import { cn } from "@/lib/utils";

/** Étiquette de champ du prototype : 12 px, 70 % du texte. */
const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label ref={ref} className={cn("field-label", className)} {...props} />
  ),
);
Label.displayName = "Label";

export { Label };
