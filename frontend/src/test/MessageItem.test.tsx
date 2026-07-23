import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AnswerVersions, BranchTurn } from "../api/types";
import { MessageItem } from "../components/MessageItem";

const turn: BranchTurn = {
  user_message: {
    id: "message-1",
    content: "原问题",
    status: "HAS_ACTIVE_ANSWER",
    logical_position: 1,
    created_at: "2026-07-23T08:00:00Z",
  },
  active_answer: {
    id: "answer-1",
    content: "当前回答",
    model_key: "MODEL_A",
    model_id: "model-a",
    selection_mode: "AUTO_ROUTE",
    status: "SUCCEEDED_ACTIVE",
    created_at: "2026-07-23T08:00:01Z",
    completed_at: "2026-07-23T08:00:02Z",
  },
};

const versions: AnswerVersions = {
  user_message_id: "message-1",
  branch_id: "branch-1",
  active_answer_version_id: "answer-1",
  items: [
    turn.active_answer!,
    {
      ...turn.active_answer!,
      id: "answer-2",
      content: "历史回答",
      status: "SUCCEEDED_INACTIVE",
      created_at: "2026-07-23T08:01:00Z",
      completed_at: "2026-07-23T08:01:01Z",
    },
  ],
};

function renderItem(overrides: Partial<Parameters<typeof MessageItem>[0]> = {}) {
  const props: Parameters<typeof MessageItem>[0] = {
    turn,
    models: [{ model_key: "MODEL_B", label: "模型 B", available: true }],
    disabled: false,
    hasLaterMessages: false,
    versions: null,
    onLoadVersions: vi.fn().mockResolvedValue(undefined),
    onRegenerate: vi.fn().mockResolvedValue(undefined),
    onActivateAnswer: vi.fn().mockResolvedValue(undefined),
    onEditMessage: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(<MessageItem {...props} />);
  return props;
}

describe("MessageItem", () => {
  it("打开弹窗前不加载回答版本", async () => {
    const props = renderItem();
    expect(props.onLoadVersions).not.toHaveBeenCalled();
    await userEvent.setup().click(screen.getByText("查看历史版本"));
    expect(props.onLoadVersions).toHaveBeenCalledWith("message-1");
  });

  it("发送三种重新生成参数", async () => {
    const props = renderItem();
    const user = userEvent.setup();
    await user.click(screen.getByText("使用原模型重新生成"));
    await user.click(screen.getByText("重新自动路由"));
    await user.selectOptions(screen.getByLabelText("重新生成使用的模型"), "MODEL_B");
    await user.click(screen.getByText("指定模型重新生成"));
    expect(props.onRegenerate).toHaveBeenNthCalledWith(
      1,
      "message-1",
      "REGENERATE_ORIGINAL_MODEL",
      null,
    );
    expect(props.onRegenerate).toHaveBeenNthCalledWith(
      2,
      "message-1",
      "REGENERATE_AUTO_ROUTE",
      null,
    );
    expect(props.onRegenerate).toHaveBeenNthCalledWith(
      3,
      "message-1",
      "REGENERATE_USER_SELECTED",
      "MODEL_B",
    );
  });

  it("编辑消息时创建自动路由分支请求", async () => {
    const props = renderItem();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "编辑消息" }));
    const editor = screen.getByLabelText("编辑消息内容");
    await user.clear(editor);
    await user.type(editor, "修改后的问题");
    await user.click(screen.getByRole("button", { name: "创建分支并生成" }));
    expect(props.onEditMessage).toHaveBeenCalledWith(
      "message-1",
      "修改后的问题",
      { selectionMode: "AUTO_ROUTE", modelKey: null },
    );
  });

  it("编辑消息时 Enter 发送，Shift+Enter 换行", async () => {
    const props = renderItem();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "编辑消息" }));
    const editor = screen.getByLabelText("编辑消息内容");
    await user.clear(editor);
    await user.type(editor, "第一行");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(editor, "第二行");

    expect(editor).toHaveValue("第一行\n第二行");
    expect(props.onEditMessage).not.toHaveBeenCalled();

    await user.keyboard("{Enter}");
    expect(props.onEditMessage).toHaveBeenCalledWith(
      "message-1",
      "第一行\n第二行",
      { selectionMode: "AUTO_ROUTE", modelKey: null },
    );
  });

  it("历史位置激活回答前二次确认", async () => {
    const props = renderItem({ versions, hasLaterMessages: true });
    const user = userEvent.setup();
    await user.click(screen.getByText("查看历史版本"));
    await user.click(screen.getByRole("button", { name: "版本 2" }));
    await user.click(screen.getByRole("button", { name: "设为当前版本" }));
    expect(props.onActivateAnswer).not.toHaveBeenCalled();
    expect(screen.getByText("从此回答创建新分支？")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "创建分支并切换" }));
    expect(props.onActivateAnswer).toHaveBeenCalledWith("message-1", "answer-2");
  });
});
