import { STRIP_CLASSES, stripKind } from "./context";

type T = Parameters<typeof stripKind>[2];

describe("colour strips by kind of requirement (FEEDBACK 'Color strip')", () => {
  const types: T = new Map([
    ["core", "core"],
    ["cmsc-bs", "major"],
    ["math-bs", "major"],
    ["econ-minor", "minor"],
    ["cmsc-bxms-1", "bxms"],
    ["civ-abroad-paris-mdd", "study_abroad_block"],
    ["premed", "preprofessional"],
    ["cmsc-ml", "specialization"],
  ]);
  const plan = ["core", "cmsc-bs", "math-bs", "econ-minor", "cmsc-bxms-1", "civ-abroad-paris-mdd", "premed", "cmsc-ml"];

  it("gives each kind of requirement its own colour, whatever the programs' order", () => {
    expect(stripKind("cmsc-bs", plan, types)).toBe("major");
    expect(stripKind("math-bs", plan, types)).toBe("second_major");
    expect(stripKind("core", plan, types)).toBe("core");
    expect(stripKind("econ-minor", plan, types)).toBe("minor");
    expect(stripKind("cmsc-bxms-1", plan, types)).toBe("graduate");
    expect(stripKind("civ-abroad-paris-mdd", plan, types)).toBe("abroad");
    expect(stripKind("premed", plan, types)).toBe("preprofessional");
    expect(stripKind("cmsc-ml", plan, types)).toBe("major"); // part of the major
    expect(stripKind("unknown", plan, types)).toBe("none");
    // The Core is yellow whether it was added first or last.
    expect(stripKind("core", [...plan].reverse(), types)).toBe("core");
  });

  it("uses distinct colours, maroon for the major", () => {
    expect(STRIP_CLASSES.major).toBe("border-l-primary");
    expect(new Set(Object.values(STRIP_CLASSES)).size).toBe(Object.keys(STRIP_CLASSES).length);
  });
});
