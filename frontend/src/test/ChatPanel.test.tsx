import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatPanel } from "../components/ChatPanel";

const conversation = {
  id: "conversation-1",
  title: "当前会话",
  latest_message_preview: null,
  updated_at: "2026-07-21T10:00:00Z",
  generation_status: "IDLE" as const,
};

describe("ChatPanel", () => {
  it("发送后把单次模型选择恢复为自动路由", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue({});
    render(
      <ChatPanel
        conversation={conversation}
        messages={[]}
        models={[{ model_key: "MODEL_B", label: "MODEL_B（Mock）", available: true }]}
        loading={false}
        submitting={false}
        error={null}
        onSend={onSend}
      />,
    );
    const selector = screen.getByLabelText("本条消息使用的模型");
    await user.selectOptions(selector, "MODEL_B");
    await user.type(screen.getByLabelText("消息内容"), "你好");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(onSend).toHaveBeenCalledWith("你好", {
      selectionMode: "USER_SELECTED",
      modelKey: "MODEL_B",
    });
    expect(selector).toHaveValue("AUTO_ROUTE");
  });

  it("展示当前回答元信息", () => {
    render(
      <ChatPanel
        conversation={conversation}
        messages={[
          {
            user_message: {
              id: "u1",
              content: "问题",
              status: "HAS_ACTIVE_ANSWER",
              logical_position: 1,
              created_at: "2026-07-21T10:00:00Z",
            },
            active_answer: {
              id: "a1",
              content: "回答",
              model_key: "MODEL_A",
              model_id: "mock-model_a",
              selection_mode: "AUTO_ROUTE",
              status: "SUCCEEDED_ACTIVE",
              created_at: "2026-07-21T10:00:00Z",
              completed_at: "2026-07-21T10:00:01Z",
            },
          },
        ]}
        models={[]}
        loading={false}
        submitting={false}
        error={null}
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByText("回答")).toBeInTheDocument();
    expect(screen.getByText("MODEL_A · 自动路由")).toBeInTheDocument();
  });

  it("发送失败时保留正文但复位单次模型选择", async () => {
    const user = userEvent.setup();
    render(
      <ChatPanel
        conversation={conversation}
        messages={[]}
        models={[{ model_key: "MODEL_B", label: "MODEL_B（Mock）", available: true }]}
        loading={false}
        submitting={false}
        error={null}
        onSend={vi.fn().mockRejectedValue(new Error("失败"))}
      />,
    );
    const input = screen.getByLabelText("消息内容");
    const selector = screen.getByLabelText("本条消息使用的模型");
    await user.selectOptions(selector, "MODEL_B");
    await user.type(input, "需要重试");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(input).toHaveValue("需要重试");
    expect(selector).toHaveValue("AUTO_ROUTE");
  });
});
