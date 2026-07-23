import { useState } from "react";

import type {
  AnswerVersions,
  BranchTurn,
  ModelOption,
  RegenerationMode,
} from "../api/types";
import type { ModelSelection } from "../hooks/useChat";
import { AnswerVersionDialog } from "./AnswerVersionDialog";
import { MessageActions } from "./MessageActions";
import { MessageEditor } from "./MessageEditor";

interface MessageItemProps {
  turn: BranchTurn;
  models: ModelOption[];
  disabled: boolean;
  hasLaterMessages: boolean;
  versions: AnswerVersions | null;
  onLoadVersions: (messageId: string) => Promise<unknown>;
  onRegenerate: (
    messageId: string,
    mode: RegenerationMode,
    modelKey: string | null,
  ) => Promise<unknown>;
  onActivateAnswer: (messageId: string, answerId: string) => Promise<unknown>;
  onEditMessage: (
    messageId: string,
    content: string,
    selection: ModelSelection,
  ) => Promise<unknown>;
}

const selectionLabels = {
  AUTO_ROUTE: "自动路由",
  AUTO_FALLBACK: "自动降级",
  USER_SELECTED: "用户指定",
};

function CopyIcon({ copied }: { copied: boolean }) {
  if (copied) {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m5 12 4 4L19 6" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="8" y="8" width="11" height="11" rx="2" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

export function MessageItem({
  turn,
  models,
  disabled,
  hasLaterMessages,
  versions,
  onLoadVersions,
  onRegenerate,
  onActivateAnswer,
  onEditMessage,
}: MessageItemProps) {
  const [copied, setCopied] = useState<"question" | "answer" | null>(null);
  const [editing, setEditing] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const messageId = turn.user_message.id;

  const copy = async (content: string, target: "question" | "answer") => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(target);
    } catch {
      setCopied(null);
    }
  };

  const openVersions = async () => {
    setVersionsOpen(true);
    if (versions) return;
    setVersionsLoading(true);
    try {
      await onLoadVersions(messageId);
    } catch {
      // 全局聊天错误区负责展示请求错误，弹窗保持可关闭。
    } finally {
      setVersionsLoading(false);
    }
  };

  const submitEdit = async (content: string, selection: ModelSelection) => {
    await onEditMessage(messageId, content, selection);
    setEditing(false);
  };

  return (
    <article className="turn">
      <div className="message user-message">
        <div className="message-heading">
          <span className="message-role">你</span>
          <div className="message-tools">
            <button
              className="edit-message-button"
              type="button"
              aria-label="编辑消息"
              title="编辑消息"
              disabled={disabled}
              onClick={() => setEditing(true)}
            >
              <EditIcon />
            </button>
            <button
              className="copy-button"
              type="button"
              aria-label="复制问题"
              title={copied === "question" ? "已复制" : "复制问题"}
              onClick={() => void copy(turn.user_message.content, "question")}
            >
              <CopyIcon copied={copied === "question"} />
            </button>
          </div>
        </div>
        {editing ? (
          <MessageEditor
            initialContent={turn.user_message.content}
            models={models}
            disabled={disabled}
            onCancel={() => setEditing(false)}
            onSubmit={submitEdit}
          />
        ) : (
          <p>{turn.user_message.content}</p>
        )}
      </div>
      <div
        className={`message assistant-message ${
          turn.active_answer ? "" : "failed-answer"
        }`}
      >
        <div className="assistant-heading">
          <span className="message-role">助手</span>
          <div className="message-tools">
            {turn.active_answer && (
              <>
                <span className="answer-meta">
                  {turn.active_answer.display_name ?? turn.active_answer.model_key} ·{" "}
                  {selectionLabels[turn.active_answer.selection_mode]}
                </span>
                <button
                  className="copy-button"
                  type="button"
                  aria-label="复制回答"
                  title={copied === "answer" ? "已复制" : "复制回答"}
                  onClick={() => void copy(turn.active_answer!.content, "answer")}
                >
                  <CopyIcon copied={copied === "answer"} />
                </button>
              </>
            )}
            <MessageActions
              hasActiveAnswer={Boolean(turn.active_answer)}
              models={models}
              disabled={disabled}
              onRegenerate={(mode, modelKey) =>
                onRegenerate(messageId, mode, modelKey)
              }
              onShowVersions={() => void openVersions()}
            />
          </div>
        </div>
        {turn.active_answer ? (
          <>
            <p>{turn.active_answer.content}</p>
            {turn.active_answer.finish_reason === "length" && (
              <p className="answer-truncated-notice" role="status">
                回答因达到长度上限而被截断，请缩小问题范围或重新生成。
              </p>
            )}
          </>
        ) : (
          <p>本轮没有生成可用回答，可从“回答操作”中重新生成。</p>
        )}
      </div>
      {versionsOpen && (
        <AnswerVersionDialog
          data={versions}
          loading={versionsLoading}
          hasLaterMessages={hasLaterMessages}
          onClose={() => setVersionsOpen(false)}
          onActivate={(answerId) => onActivateAnswer(messageId, answerId)}
        />
      )}
    </article>
  );
}
