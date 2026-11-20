import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

/*
 * DESIGN.md buttons: pills, `button` type. Redesign 2026-11-20 ("Maroon and night"): bigger, like
 * the reference's Login pill: 46px tall inside a 52px box, 16px semibold.
 *
 * Accessibility keeps a generous target: the element is 52px tall and draws its pill inside a
 * transparent border (`bg-clip-padding`), so the visible pill is 46px (36px for `sm`, in a 44px
 * box) while the hit area and the bounding box stay larger. Outline pills draw their 1px line as an inset shadow,
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
        // Disabled: a grey plate with muted text (still legible, 4.7:1), not a faded maroon that reads as active (D11 AD-4).
        primary:
          "bg-primary text-on-primary hover:bg-primary-hover active:bg-primary-active disabled:bg-surface-strong disabled:text-muted disabled:opacity-100 aria-disabled:bg-surface-strong aria-disabled:text-muted aria-disabled:opacity-100",
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
        /** On the night background: a white pill with maroon text. */
        light: "bg-on-night text-primary hover:bg-on-night-soft active:bg-on-night-soft",
        /** On the night background: a clear pill with a soft white line. */
        night:
          "bg-transparent text-on-night shadow-[inset_0_0_0_1px_rgb(255_255_255/0.35)] hover:bg-on-night/10 active:bg-on-night/15",
      },
      size: {
        /** 46px pill in a 52px box. */
        md: "min-h-[52px] border-[3px] px-6 focus-visible:outline-offset-[-1px]",
        /** 36px pill in a 44px box (chips, dense rows). */
        sm: "min-h-11 border-4 px-3 text-caption font-semibold focus-visible:outline-offset-[-2px]",
        /** 44px circle in a 48px box. */
        icon: "size-12 border-2 p-0 focus-visible:outline-offset-0",
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
