import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/** DESIGN.md token names that tailwind-merge must know, so `text-caption` (a size) and
 *  `text-ink` (a color) do not cancel each other. Keep in sync with `@theme` in index.css. */
export const TYPE_TOKENS = [
  "display-mega",
  "display-xl",
  "display-lg",
  "display-md",
  "display-sm",
  "title-md",
  "title-sm",
  "body-md",
  "body-strong",
  "body-sm",
  "caption",
  "caption-uppercase",
  "button",
  "nav-link",
];

const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: TYPE_TOKENS,
      radius: ["xs", "sm", "md", "lg", "xl", "xxl", "pill"],
      shadow: ["hover", "overlay"],
      container: ["content", "reading", "form", "tool"],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
