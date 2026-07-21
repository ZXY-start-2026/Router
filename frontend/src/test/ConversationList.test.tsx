import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConversationList } from "../components/ConversationList";

const item = {
  id: "conversation-1",
  title: "测试会话",
  latest_message_preview: "最近一条消息",
  updated_at: "2026-07-21T10:00:00Z",
  generation_status: "SUCCEEDED" as const,
};

describe("ConversationList", () => {
  it("展示会话摘要并允许选择", () => {
    const onSelect = vi.fn();
    render(
      <ConversationList
        items={[item]}
        currentId={null}
        loading={false}
        hasMore={false}
        error={null}
        onSelect={onSelect}
        onCreate={vi.fn()}
        onLoadMore={vi.fn()}
      />,
    );
    expect(screen.getByText("测试会话")).toBeInTheDocument();
    expect(screen.getByText("最近一条消息")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /测试会话/ }));
    expect(onSelect).toHaveBeenCalledWith("conversation-1");
  });

  it("滚动到底部时加载更多", () => {
    const onLoadMore = vi.fn();
    const { container } = render(
      <ConversationList
        items={[item]}
        currentId={null}
        loading={false}
        hasMore
        error={null}
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onLoadMore={onLoadMore}
      />,
    );
    const scrollArea = container.querySelector(".conversation-scroll")!;
    Object.defineProperties(scrollArea, {
      scrollHeight: { configurable: true, value: 100 },
      scrollTop: { configurable: true, value: 50 },
      clientHeight: { configurable: true, value: 50 },
    });
    fireEvent.scroll(scrollArea);
    expect(onLoadMore).toHaveBeenCalledOnce();
  });
});
