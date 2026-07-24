import { useEffect, useState } from "react";

import type { CurrentMemory, MemoryVersions } from "../api/types";
import { ConfirmationDialog } from "./ConfirmationDialog";

interface MemoryPanelProps {
  memory: CurrentMemory | null;
  versions: MemoryVersions | null;
  disabled: boolean;
  onLoadVersions: () => Promise<unknown>;
  onSave: (text: string) => Promise<unknown>;
  onRestore: (versionId: string) => Promise<unknown>;
}

const VERSION_LABELS = {
  INITIAL_SYSTEM_SUMMARY: "首次系统摘要",
  INCREMENTAL_SYSTEM_UPDATE: "增量系统更新",
  USER_EDIT: "用户编辑",
  RESTORE: "历史恢复",
  BRANCH_INHERIT: "分支继承",
} as const;

export function MemoryPanel({
  memory,
  versions,
  disabled,
  onLoadVersions,
  onSave,
  onRestore,
}: MemoryPanelProps) {
  const [draft, setDraft] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [restoreId, setRestoreId] = useState<string | null>(null);

  useEffect(() => {
    setDraft(memory?.current?.protected_user_text ?? "");
  }, [memory?.current?.id, memory?.current?.protected_user_text]);

  const conflicts = memory?.current?.conflict_metadata.items ?? [];
  const conflictStatus = memory?.current?.conflict_metadata.status;

  return (
    <div className="settings-panel">
      <div className="panel-summary-row">
        <span>
          {memory?.current
            ? `版本 ${memory.current.version_number} · ${
                VERSION_LABELS[memory.current.type]
              }`
            : "尚无备忘录版本"}
        </span>
        <span>
          规则 {memory?.config.n ?? 10}/{memory?.config.k ?? 5}/
          {memory?.config.m ?? 5}
        </span>
      </div>

      {memory?.latest_update?.status === "FAILED" ? (
        <p className="panel-warning">
          最近一次自动更新失败：
          {memory.latest_update.error_message ?? "模型未能生成有效摘要"}
        </p>
      ) : null}

      {conflictStatus === "UNKNOWN" ? (
        <p className="panel-warning">保护区冲突尚未完成检测，请人工确认。</p>
      ) : null}
      {conflicts.length ? (
        <div className="panel-warning">
          <strong>发现潜在冲突</strong>
          <ul>
            {conflicts.map((item, index) => (
              <li key={`${item.dialogue_position ?? "unknown"}-${index}`}>
                {item.description}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <label className="panel-field">
        <span>用户保护区</span>
        <textarea
          rows={7}
          value={draft}
          disabled={disabled}
          placeholder="记录不能被系统自动修改的偏好、约束或长期事实"
          onChange={(event) => setDraft(event.target.value)}
        />
      </label>
      <p className="panel-help">系统只读取此区域；每次保存都会创建新版本。</p>
      <button
        className="panel-primary-button"
        type="button"
        disabled={disabled}
        onClick={() => void onSave(draft).catch(() => undefined)}
      >
        保存保护区
      </button>

      <label className="panel-field">
        <span>系统摘要（只读）</span>
        <textarea
          rows={8}
          readOnly
          value={memory?.current?.system_summary ?? ""}
          placeholder="达到完整轮次阈值后由系统生成"
        />
      </label>
      <p className="panel-help">
        当前覆盖位置：
        {memory?.current?.covered_through_position ?? "尚未开始摘要"}
      </p>

      <div className="panel-section-heading">
        <h3>版本历史</h3>
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            setShowHistory(true);
            void onLoadVersions().catch(() => undefined);
          }}
        >
          {showHistory ? "刷新历史" : "查看历史"}
        </button>
      </div>
      {showHistory ? (
        <div className="memory-version-list">
          {versions?.items.map((version) => (
            <article key={version.id} className="memory-version-card">
              <div>
                <strong>版本 {version.version_number}</strong>
                <span>{VERSION_LABELS[version.type]}</span>
              </div>
              <p>
                覆盖至 {version.covered_through_position ?? "无"} ·{" "}
                {new Date(version.created_at).toLocaleString()}
              </p>
              <button
                type="button"
                disabled={disabled || version.is_current}
                onClick={() => setRestoreId(version.id)}
              >
                {version.is_current ? "当前版本" : "恢复此版本"}
              </button>
            </article>
          ))}
          {versions && !versions.items.length ? <p>暂无历史版本。</p> : null}
        </div>
      ) : null}

      {restoreId ? (
        <ConfirmationDialog
          title="恢复备忘录版本？"
          description="系统会创建新的恢复版本，现有版本和历史记录不会被删除。"
          confirmLabel="创建恢复版本"
          onCancel={() => setRestoreId(null)}
          onConfirm={() => {
            const versionId = restoreId;
            setRestoreId(null);
            void onRestore(versionId).catch(() => undefined);
          }}
        />
      ) : null}
    </div>
  );
}
