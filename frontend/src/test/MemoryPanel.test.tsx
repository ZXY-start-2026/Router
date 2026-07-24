import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MemoryPanel } from "../components/MemoryPanel";

describe("MemoryPanel", () => {
  it("只提交用户保护区并按需加载历史", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onLoadVersions = vi.fn().mockResolvedValue(undefined);
    render(
      <MemoryPanel
        memory={{
          branch_id: "branch-1",
          current: null,
          latest_update: null,
          config: { n: 10, k: 5, m: 5 },
        }}
        versions={null}
        disabled={false}
        onLoadVersions={onLoadVersions}
        onSave={onSave}
        onRestore={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText("用户保护区"), "始终使用中文");
    await user.click(screen.getByRole("button", { name: "保存保护区" }));
    expect(onSave).toHaveBeenCalledWith("始终使用中文");
    expect(onLoadVersions).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "查看历史" }));
    expect(onLoadVersions).toHaveBeenCalledTimes(1);
  });
});
