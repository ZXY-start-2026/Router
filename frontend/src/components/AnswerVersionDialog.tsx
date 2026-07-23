import { useEffect, useMemo, useState } from "react";

import type { AnswerVersions } from "../api/types";
import { ConfirmationDialog } from "./ConfirmationDialog";

interface AnswerVersionDialogProps {
  data: AnswerVersions | null;
  loading: boolean;
  hasLaterMessages: boolean;
  onClose: () => void;
  onActivate: (answerId: string) => Promise<unknown>;
}

export function AnswerVersionDialog({
  data,
  loading,
  hasLaterMessages,
  onClose,
  onActivate,
}: AnswerVersionDialogProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [activating, setActivating] = useState(false);

  useEffect(() => {
    setSelectedId(data?.active_answer_version_id ?? data?.items[0]?.id ?? null);
  }, [data]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !pendingId && !activating) onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [activating, onClose, pendingId]);

  const selected = useMemo(
    () => data?.items.find((item) => item.id === selectedId) ?? null,
    [data, selectedId],
  );

  const activate = async (answerId: string) => {
    setActivating(true);
    try {
      await onActivate(answerId);
      onClose();
    } catch {
      // 全局聊天错误区负责展示请求错误，弹窗保持打开以便重试。
    } finally {
      setActivating(false);
      setPendingId(null);
    }
  };

  const requestActivation = () => {
    if (!selected || selected.id === data?.active_answer_version_id) return;
    if (hasLaterMessages) setPendingId(selected.id);
    else void activate(selected.id);
  };

  return (
    <>
      <div
        className="dialog-backdrop"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget && !activating) onClose();
        }}
      >
        <section
          className="answer-version-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="answer-version-title"
        >
          <div className="version-dialog-heading">
            <div>
              <span className="eyebrow">ANSWER HISTORY</span>
              <h2 id="answer-version-title">回答历史版本</h2>
            </div>
            <button type="button" disabled={activating} onClick={onClose}>
              关闭
            </button>
          </div>
          {loading && <p className="loading-line">正在加载版本…</p>}
          {!loading && data && !data.items.length && (
            <p className="empty-list">暂无成功回答版本</p>
          )}
          {data && data.items.length > 0 && (
            <div className="version-dialog-content">
              <div className="version-list" aria-label="回答版本列表">
                {data.items.map((answer, index) => (
                  <button
                    type="button"
                    key={answer.id}
                    className={answer.id === selectedId ? "active" : ""}
                    onClick={() => setSelectedId(answer.id)}
                  >
                    版本 {index + 1}
                    {answer.id === data.active_answer_version_id ? " · 当前" : ""}
                  </button>
                ))}
              </div>
              <div className="version-preview">
                {selected && (
                  <>
                    <p className="answer-meta">
                      {selected.display_name ?? selected.model_key} ·{" "}
                      {new Date(selected.created_at).toLocaleString("zh-CN")}
                    </p>
                    <p>{selected.content}</p>
                    <button
                      type="button"
                      disabled={
                        activating ||
                        selected.id === data.active_answer_version_id
                      }
                      onClick={requestActivation}
                    >
                      {selected.id === data.active_answer_version_id
                        ? "当前版本"
                        : "设为当前版本"}
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
      {pendingId && (
        <ConfirmationDialog
          title="从此回答创建新分支？"
          description="该回答之后已有消息。设为当前版本会从这里创建新分支，原分支不会改变。"
          confirmLabel={activating ? "切换中…" : "创建分支并切换"}
          onCancel={() => setPendingId(null)}
          onConfirm={() => void activate(pendingId)}
        />
      )}
    </>
  );
}
