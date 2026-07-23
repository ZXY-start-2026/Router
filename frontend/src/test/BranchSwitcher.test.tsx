import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Branch } from "../api/types";
import { BranchSwitcher } from "../components/BranchSwitcher";

const root: Branch = {
  id: "root",
  parent_branch_id: null,
  branch_point_type: "ROOT",
  branch_point_message_id: null,
  branch_point_answer_version_id: null,
  complete_turn_count: 1,
  created_at: "2026-07-23T08:00:00Z",
  is_active: true,
};

const edited: Branch = {
  ...root,
  id: "edited",
  parent_branch_id: "root",
  branch_point_type: "USER_MESSAGE_EDIT",
  branch_point_message_id: "message-1",
  created_at: "2026-07-23T08:01:00Z",
  is_active: false,
};

describe("BranchSwitcher", () => {
  it("单分支时隐藏", () => {
    render(
      <BranchSwitcher
        branches={[root]}
        activeId="root"
        disabled={false}
        onActivate={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("当前分支")).not.toBeInTheDocument();
  });

  it("选择其他分支时通知调用方", async () => {
    const onActivate = vi.fn().mockResolvedValue(undefined);
    render(
      <BranchSwitcher
        branches={[root, edited]}
        activeId="root"
        disabled={false}
        onActivate={onActivate}
      />,
    );
    await userEvent.setup().selectOptions(screen.getByLabelText("当前分支"), "edited");
    expect(onActivate).toHaveBeenCalledWith("edited");
    expect(screen.getByRole("option", { name: "分支 2 · 编辑消息" })).toBeInTheDocument();
  });
});
