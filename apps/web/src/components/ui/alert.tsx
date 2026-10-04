import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

/** Bandeau du prototype : bleu clair pour l'information, les succès et les erreurs (aucun rouge). */
const alertVariants = cva("notice", {
  variants: {
    variant: {
      default: "",
      destructive: "",
      success: "",
    },
  },
  defaultVariants: { variant: "default" },
});

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>
>(({ className, variant, ...props }, ref) => (
  <div ref={ref} className={cn(alertVariants({ variant }), className)} {...props} />
));
Alert.displayName = "Alert";

export { Alert, alertVariants };
