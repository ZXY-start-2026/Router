import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { HIDDEN_CONVERSATION_IDS_KEY } from "../storage/hiddenConversations";

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

  it("确认删除后在当前浏览器持久隐藏会话", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      const body = url.endsWith("/models")
        ? []
        : {
            items: [
              {
                id: "conversation-1",
                title: "待隐藏会话",
                latest_message_preview: "这条会话只在前端隐藏",
                updated_at: "2026-07-21T10:00:00Z",
                generation_status: "SUCCEEDED",
              },
            ],
            next_cursor: null,
            has_more: false,
          };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const view = render(<App />);
    expect(await screen.findByText("待隐藏会话")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "删除会话“待隐藏会话”" }));
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(screen.queryByText("待隐藏会话")).not.toBeInTheDocument());
    expect(JSON.parse(window.localStorage.getItem(HIDDEN_CONVERSATION_IDS_KEY) ?? "[]")).toEqual([
      "conversation-1",
    ]);

    view.unmount();
    render(<App />);
    await waitFor(() => {
      const conversationRequests = fetchMock.mock.calls.filter(([input]) =>
        String(input).includes("/conversations?"),
      );
      expect(conversationRequests).toHaveLength(2);
    });
    expect(screen.queryByText("待隐藏会话")).not.toBeInTheDocument();
  });
});
