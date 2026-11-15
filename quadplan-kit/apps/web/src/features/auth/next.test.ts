import { safeNext } from "./next";

describe("safeNext", () => {
  it.each([
    ["/courses/CMSC%2014100/i/demo-instructor-a", "/courses/CMSC%2014100/i/demo-instructor-a"],
    ["/plans?x=1", "/plans?x=1"],
    [null, "/plan"],
    ["", "/plan"],
    ["https://evil.example/", "/plan"],
    ["//evil.example/", "/plan"],
    ["/\\evil.example", "/plan"],
    ["/login", "/plan"],
    ["/signup?next=/x", "/plan"],
  ])("%s -> %s", (raw, expected) => {
    expect(safeNext(raw)).toBe(expected);
  });
});
