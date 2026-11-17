import { studyAbroadProgramFor, TERM_PRESETS } from "./goals";

const catalog = [
  { id: "cs-bs", type: "major" },
  { id: "abroad-cordoba", type: "study_abroad_block" },
  { id: "abroad-paris", type: "study_abroad_block" },
];

describe("study abroad goal", () => {
  it("prefers the study-abroad program already on the plan", () => {
    expect(studyAbroadProgramFor(["cs-bs", "abroad-paris"], catalog)).toBe("abroad-paris");
  });

  it("falls back to the first study-abroad program in the catalog", () => {
    expect(studyAbroadProgramFor(["cs-bs"], catalog)).toBe("abroad-cordoba");
  });

  it("has no program when the catalog has no study-abroad block", () => {
    expect(studyAbroadProgramFor(["cs-bs"], [{ id: "cs-bs", type: "major" }])).toBeUndefined();
  });

  it("makes the goal for the chosen program and quarter", () => {
    const preset = TERM_PRESETS.find((p) => p.key === "study_abroad")!;
    const goal = preset.make("2027-AU", { studyAbroadProgram: studyAbroadProgramFor(["abroad-paris"], catalog) });
    expect(goal).toMatchObject({ type: "study_abroad", abroad_term: "2027-AU", program_id: "abroad-paris" });
  });
});
