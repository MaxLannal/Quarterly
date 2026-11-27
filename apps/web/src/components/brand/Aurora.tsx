import "./aurora.css";

/**
 * The night behind every page (docs/DESIGN.md "Dark glass"): a ring of white light crossing rings
 * of crimson and maroon light, the way light bends round the rim of a planet. Each ring is a
 * circle whose bright arc travels slowly round it; where a white arc crosses a red one they add up
 * (screen blend), so the crossing glows rose-white. Only transforms animate (the compositor moves
 * cached layers), so the motion costs almost nothing. Reduced motion: the light holds still.
 *
 * `intensity="bright"` is for pages that sit straight on the night (the homepage, sign-in);
 * elsewhere the light is dimmer, because a pane of glass covers most of it.
 */
export function Aurora({ intensity = "dim" }: { intensity?: "dim" | "bright" }) {
  return (
    <div aria-hidden="true" className="aurora" data-intensity={intensity}>
      <div className="aurora-bloom aurora-bloom-maroon" />
      <div className="aurora-bloom aurora-bloom-crimson" />
      <div className="aurora-orbit aurora-orbit-haze">
        <div className="aurora-spin">
          <i className="aurora-ring aurora-ring-haze" />
        </div>
      </div>
      <div className="aurora-orbit aurora-orbit-red">
        <div className="aurora-spin">
          <i className="aurora-ring aurora-ring-red-soft" />
          <i className="aurora-ring aurora-ring-red-core" />
        </div>
      </div>
      <div className="aurora-orbit aurora-orbit-white">
        <div className="aurora-spin">
          <i className="aurora-ring aurora-ring-white-soft" />
          <i className="aurora-ring aurora-ring-white-core" />
        </div>
      </div>
      <div className="aurora-grain" />
      <div className="aurora-vignette" />
    </div>
  );
}
