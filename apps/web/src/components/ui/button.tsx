import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

/*
 * Buttons ("Simple light", docs/DESIGN.md): soft rounded rectangles, 15px semibold. The main
 * button is black with white text (one per view); the others are white with a hairline, or bare.
 * Every button is a 44px target. `sm` draws a 36px button inside a transparent border, so its hit
 * area stays 44px; the focus ring is pulled in to sit round the drawn button.
 */
export const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-lg",
    "border-transparent bg-clip-padding font-sans text-button transition-[color,background-color,box-shadow,scale] duration-150 active:scale-[0.98]",
    "disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50",
  ],
  {
    variants: {
      variant: {
        /** button-primary: black, one per view. Disabled: a grey plate with muted text (D11 AD-4). */
        primary:
          "bg-ink text-on-primary hover:bg-primary-hover active:bg-primary-active disabled:bg-surface-strong disabled:text-muted disabled:opacity-100 aria-disabled:bg-surface-strong aria-disabled:text-muted aria-disabled:opacity-100",
        /** button-outline: white with a hairline. */
        outline:
          "bg-canvas text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-canvas-soft active:bg-surface-strong",
        /** button-tertiary-text: no chrome; a soft plate on hover. */
        ghost: "bg-transparent text-ink hover:bg-surface-strong active:bg-hairline",
        /** button-destructive: outline with error-coloured text; never an error fill. */
        destructive:
          "bg-canvas text-error shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-error-wash active:bg-error-wash",
        /** link-inline as a button. */
        link: "rounded-xs bg-transparent text-ink underline decoration-hairline-strong underline-offset-4 hover:decoration-ink",
        /** Kept for older markup that sat on a dark band: now the same as outline. */
        light:
          "bg-canvas text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-canvas-soft active:bg-surface-strong",
        night:
          "bg-canvas text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-canvas-soft active:bg-surface-strong",
      },
      size: {
        /** 44px. */
        md: "min-h-11 px-5",
        /** 36px drawn in a 44px box (chips, dense rows). */
        sm: "min-h-11 border-4 px-3 text-caption font-semibold rounded-[14px] focus-visible:outline-offset-[-2px]",
        /** 44px square. */
        icon: "size-11 p-0",
      },
    },
    compoundVariants: [{ variant: "link", size: ["md", "sm"], class: "px-1" }],
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type Variant = NonNullable<VariantProps<typeof buttonVariants>["variant"]> | "default";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    Omit<VariantProps<typeof buttonVariants>, "variant"> {
  /** `default` is kept as an alias of `primary` (shadcn/ui naming). */
  variant?: Variant | null;
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    const v = variant === "default" ? "primary" : variant;
    return <Comp ref={ref} className={cn(buttonVariants({ variant: v, size }), className)} {...props} />;
  },
);
Button.displayName = "Button";
