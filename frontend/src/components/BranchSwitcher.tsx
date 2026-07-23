import type { Branch } from "../api/types";

interface BranchSwitcherProps {
  branches: Branch[];
  activeId: string | null;
  disabled: boolean;
  onActivate: (branchId: string) => Promise<unknown>;
}

const branchTypeLabels = {
  ROOT: "主分支",
  USER_MESSAGE_EDIT: "编辑消息",
  ANSWER_VERSION_ACTIVATE: "回答版本",
};

export function BranchSwitcher({
  branches,
  activeId,
  disabled,
  onActivate,
}: BranchSwitcherProps) {
  if (branches.length <= 1 || !activeId) return null;

  return (
    <label className="branch-switcher">
      <span>当前分支</span>
      <select
        aria-label="当前分支"
        value={activeId}
        disabled={disabled}
        onChange={(event) => {
          void onActivate(event.target.value).catch(() => undefined);
        }}
      >
        {branches.map((branch, index) => (
          <option key={branch.id} value={branch.id}>
            {branch.branch_point_type === "ROOT"
              ? branchTypeLabels.ROOT
              : `分支 ${index + 1} · ${branchTypeLabels[branch.branch_point_type]}`}
          </option>
        ))}
      </select>
    </label>
  );
}
