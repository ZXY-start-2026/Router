import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RolePanel } from "../components/RolePanel";

describe("RolePanel", () => {
  it("选择模板只填充表单，保存时才创建角色版本", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <RolePanel
        role={null}
        templates={[
          {
            id: "template-1",
            name: "架构师",
            persona: "务实",
            background: "",
            domain: "软件架构",
            traits: ["严谨"],
            style: "简洁",
            constraints_text: "",
            created_at: "2026-07-24T00:00:00Z",
          },
        ]}
        disabled={false}
        onLoadTemplates={vi.fn().mockResolvedValue(undefined)}
        onSave={onSave}
        onDeactivate={vi.fn()}
        onCreateTemplate={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByLabelText("从模板填充"), "template-1");
    expect(screen.getByLabelText("角色名称")).toHaveValue("架构师");
    expect(onSave).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "保存角色" }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "架构师",
        domain: "软件架构",
        source_template_id: "template-1",
      }),
    );
  });
});
