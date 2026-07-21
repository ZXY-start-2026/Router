import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";

describe("App", () => {
  afterEach(() => vi.restoreAllMocks());

  it("无会话时展示开始引导", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      const body = url.endsWith("/models")
        ? []
        : { items: [], next_cursor: null, has_more: false };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    render(<App />);
    expect(await screen.findByText("从一个问题开始")).toBeInTheDocument();
    expect(await screen.findByText("创建一个会话开始聊天")).toBeInTheDocument();
  });
});

