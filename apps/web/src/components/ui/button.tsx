import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Boutons du prototype : `default` = primaire (accent), `outline` = secondaire (filet), `ghost` = lien discret.
 * Les boutons primaires d'action principale portent le cadre « blueprint » (croix d'angle) via `blueprint`.
 */
const buttonVariants = cva("btn", {
  variants: {
    variant: {
      default: "btn-primary",
      outline: "btn-secondary",
      ghost: "btn-ghost",
      link: "btn-ghost",
    },
    size: {
      default: "",
      sm: "!px-[10px] !py-1",
      lg: "!py-[10px]",
      icon: "btn-icon",
    },
  },
  defaultVariants: { variant: "default", size: "default" },
});

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Ajoute les repères d'angle du prototype (bouton primaire d'une page ou d'un formulaire). */
  blueprint?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, blueprint = false, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), blueprint && "blueprint", className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";

export { Button, buttonVariants };
