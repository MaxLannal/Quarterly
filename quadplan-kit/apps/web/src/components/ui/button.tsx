import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

/*
 * DESIGN.md buttons: pills, `button` type, 40px tall with 10x20px padding.
 *
 * Accessibility keeps a 44px target: the element is 44px tall and draws its pill inside a
 * transparent border (`bg-clip-padding`), so the visible pill is 40px (32px for `sm`) while the
 * hit area and the bounding box stay 44px. Outline pills draw their 1px line as an inset shadow,
 * which sits inside that transparent border. The focus ring is pulled in by the same amount, so
 * it reads as DESIGN.md's "2px ring, 2px offset" around the visible pill.
 */
export const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-pill",
    // Press feedback: the pill dips to 97% for the 150ms press (instant under reduced motion).
    "border-transparent bg-clip-padding font-sans text-button transition-[color,background-color,box-shadow,scale] active:scale-[0.97]",
    "disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50",
  ],
  {
    variants: {
      variant: {
        /** button-primary: maroon pill, one per view. */
        primary: "bg-primary text-on-primary hover:bg-primary-hover active:bg-primary-active",
        /** button-outline: transparent pill, 1px hairline-strong line, ink text. */
        outline:
          "bg-transparent text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-surface-strong active:bg-hairline",
        /** button-tertiary-text: ink text, no chrome (a soft plate on hover only). */
        ghost: "bg-transparent text-ink hover:bg-surface-strong active:bg-hairline",
        /** button-destructive: outline pill with error-colored text; never an error fill. */
        destructive:
          "bg-transparent text-error shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-error-wash active:bg-error-wash",
        /** link-inline as a button: maroon, underlined. */
        link: "rounded-xs bg-transparent text-primary underline underline-offset-4 hover:text-primary-hover",
      },
      size: {
        /** 40px pill in a 44px box. */
        md: "min-h-11 border-2 px-[18px] focus-visible:outline-offset-0",
        /** 32px pill in a 44px box (chips, dense rows). */
        sm: "min-h-11 border-[6px] px-[6px] text-caption font-medium focus-visible:outline-offset-[-4px]",
        /** 40px circle in a 44px box. */
        icon: "size-11 border-2 p-0 focus-visible:outline-offset-0",
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
