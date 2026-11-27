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
    "border-transparent bg-clip-padding font-sans text-button transition-[color,background-color,box-shadow,scale] duration-200 active:scale-[0.97]",
    "disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50",
  ],
  {
    variants: {
      variant: {
        /** button-primary: one per view. A white pill with a red glow beneath it, like light through
         * glass (docs/DESIGN.md "Dark glass"); the glow brightens on hover. */
        // Disabled: a dim glass plate with muted text (still legible), not a faded white that reads as active (D11 AD-4).
        primary:
          "bg-ink text-canvas shadow-[0_8px_30px_rgb(255_60_90/0.28),inset_0_-2px_0_rgb(0_0_0/0.08)] hover:bg-white hover:shadow-[0_10px_40px_rgb(255_60_90/0.45),inset_0_-2px_0_rgb(0_0_0/0.08)] active:bg-on-night-soft disabled:bg-surface-strong disabled:text-muted disabled:shadow-none disabled:opacity-100 aria-disabled:bg-surface-strong aria-disabled:text-muted aria-disabled:shadow-none aria-disabled:opacity-100",
        /** button-outline: a clear glass pill with a lit edge. */
        outline:
          "bg-white/[0.035] text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong),inset_0_1px_0_rgb(255_255_255/0.08)] hover:bg-white/[0.08] hover:shadow-[inset_0_0_0_1px_rgb(255_255_255/0.28),inset_0_1px_0_rgb(255_255_255/0.1)] active:bg-white/[0.12]",
        /** button-tertiary-text: ink text, no chrome (a soft plate on hover only). */
        ghost: "bg-transparent text-ink hover:bg-surface-strong active:bg-white/[0.12]",
        /** button-destructive: outline pill with error-coloured text; never an error fill. */
        destructive:
          "bg-transparent text-error shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-error-wash active:bg-error-wash",
        /** link-inline as a button: the red light, underlined. */
        link: "rounded-xs bg-transparent text-primary underline underline-offset-4 hover:text-primary-hover",
        /** On the night: the same white pill as primary. */
        light:
          "bg-ink text-canvas shadow-[0_8px_30px_rgb(255_60_90/0.28)] hover:bg-white active:bg-on-night-soft",
        /** On the night: a clear pill with a soft white line. */
        night:
          "bg-transparent text-on-night shadow-[inset_0_0_0_1px_rgb(255_255_255/0.3)] hover:bg-on-night/10 active:bg-on-night/15",
        /** Red glass: for a second strong action beside the white pill (e.g. "Generate"). */
        glow:
          "bg-[linear-gradient(180deg,rgb(255_92_112/0.32),rgb(160_16_44/0.32))] text-ink shadow-[inset_0_0_0_1px_rgb(255_120_140/0.45),inset_0_1px_0_rgb(255_255_255/0.18),0_8px_28px_rgb(200_20_50/0.3)] hover:bg-[linear-gradient(180deg,rgb(255_92_112/0.45),rgb(160_16_44/0.42))]",
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
