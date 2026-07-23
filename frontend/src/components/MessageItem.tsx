import { useState } from "react";

import type { BranchTurn } from "../api/types";

interface MessageItemProps {
  turn: BranchTurn;
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

export function MessageItem({ turn }: MessageItemProps) {
  const [copied, setCopied] = useState<"question" | "answer" | null>(null);

  const copy = async (content: string, target: "question" | "answer") => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(target);
    } catch {
      setCopied(null);
    }
  };

  return (
    <article className="turn">
      <div className="message user-message">
        <div className="message-heading">
          <span className="message-role">你</span>
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
        <p>{turn.user_message.content}</p>
      </div>
      {turn.active_answer ? (
        <div className="message assistant-message">
          <div className="assistant-heading">
            <span className="message-role">助手</span>
            <div className="message-tools">
              <span className="answer-meta">
                {turn.active_answer.display_name ?? turn.active_answer.model_key} · {selectionLabels[turn.active_answer.selection_mode]}
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
            </div>
          </div>
          <p>{turn.active_answer.content}</p>
          {turn.active_answer.finish_reason === "length" ? (
            <p className="answer-truncated-notice" role="status">
              回答因达到长度上限而被截断，请缩小问题范围或重新生成。
            </p>
          ) : null}
        </div>
      ) : (
        <div className="message assistant-message failed-answer">
          <span className="message-role">助手</span>
          <p>本轮没有生成可用回答。</p>
        </div>
      )}
    </article>
  );
}
