import { http, HttpResponse } from "msw";
import { server } from "@/mocks/node";
import { emptyPlan } from "@/features/planner/planModel";
import { NotAvailableError } from "./client";
import { parseSseChunk, streamPlanner } from "./sse";

describe("SSE", () => {
  it("splits complete events and keeps the rest", () => {
    expect(parseSseChunk('data: {"a":1}\n\ndata: {"b"')).toEqual({ events: ['{"a":1}'], rest: 'data: {"b"' });
    expect(parseSseChunk("event: x\r\ndata: 1\r\ndata: 2\r\n\r\n").events).toEqual(["1\n2"]);
  });

  it("streamPlanner parses question, plan and proposal events", async () => {
    const asked: string[] = [];
    for await (const ev of streamPlanner({ mode: "generate", plan: emptyPlan("2099-00") })) asked.push(ev.type);
    expect(asked).toEqual(["step", "step", "question", "done"]);

    const types: string[] = [];
    const titles: string[] = [];
    const body = { mode: "generate" as const, plan: emptyPlan("2099-00"), profile_answers: { interests: ["testing"] } };
    for await (const ev of streamPlanner(body)) {
      types.push(ev.type);
      if (ev.type === "proposal") titles.push(ev.title);
    }
    expect(types.filter((t) => t !== "step")).toEqual(["plan", "proposal", "proposal", "proposal", "done"]);
    expect(titles).toEqual(["Test introductory sequence", "Test methods", "Electives for testing"]);
  });

  it("streams a chat answer with a proposal", async () => {
    const types: string[] = [];
    for await (const ev of streamPlanner({ mode: "chat", message: "please add", plan: emptyPlan("2099-00") })) types.push(ev.type);
    expect(types).toEqual(["message", "proposal", "done"]);
  });

  it("throws NotAvailableError on 501", async () => {
    server.use(http.post("*/api/agents/planner", () => HttpResponse.json({ detail: "Not implemented yet (prompt 07)" }, { status: 501 })));
    const run = async () => {
      for await (const ev of streamPlanner({ mode: "chat", message: "hi", plan: emptyPlan("2099-00") })) void ev;
    };
    await expect(run()).rejects.toBeInstanceOf(NotAvailableError);
  });
});
