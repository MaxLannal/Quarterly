import { http, HttpResponse } from "msw";
import { server } from "@/mocks/node";
import { emptyPlan } from "@/features/planner/planModel";
import { NotAvailableError } from "./client";
import { parseSseChunk, streamChat } from "./sse";

describe("SSE", () => {
  it("splits complete events and keeps the rest", () => {
    expect(parseSseChunk('data: {"a":1}\n\ndata: {"b"')).toEqual({ events: ['{"a":1}'], rest: 'data: {"b"' });
    expect(parseSseChunk("event: x\r\ndata: 1\r\ndata: 2\r\n\r\n").events).toEqual(["1\n2"]);
  });

  it("streams agent events", async () => {
    const types: string[] = [];
    for await (const ev of streamChat({ message: "please add", plan: emptyPlan("2099-00"), history: [] })) types.push(ev.type);
    expect(types).toEqual(["message", "proposal", "done"]);
  });

  it("throws NotAvailableError on 501", async () => {
    server.use(http.post("*/api/agents/chat", () => HttpResponse.json({ detail: "Not implemented yet (prompt 07)" }, { status: 501 })));
    const run = async () => {
      for await (const ev of streamChat({ message: "hi", plan: emptyPlan("2099-00"), history: [] })) void ev;
    };
    await expect(run()).rejects.toBeInstanceOf(NotAvailableError);
  });
});
