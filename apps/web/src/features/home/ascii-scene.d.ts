// Types for <ascii-scene> (public/ascii-scene/ascii-scene.js; FEEDBACK "ASCII Scene").
import type { CSSProperties } from "react";

type AsciiSceneAttrs = {
  src?: string;
  theme?: "paper" | "dark";
  time?:
    | "auto"
    | "cycle"
    | "dawn"
    | "morning"
    | "noon"
    | "golden"
    | "dusk"
    | "night"
    | `${number}:${number}`;
  weather?: "auto" | "clear" | "cloudy" | "rain" | "storm" | "snow" | "fog";
  /** Quarterly addition: the site's own weather endpoint ({weather_code, cloud_cover}). */
  "weather-src"?: string;
  controls?: "" | "false";
  density?: "low" | "medium" | "high" | `${number}`;
  fade?: number | string;
  timezone?: string;
  label?: string;
  class?: string;
  style?: CSSProperties;
  id?: string;
};

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "ascii-scene": AsciiSceneAttrs;
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "ascii-scene": HTMLElement & {
      setTime(v: string): void;
      setWeather(v: string): void;
    };
  }
}
