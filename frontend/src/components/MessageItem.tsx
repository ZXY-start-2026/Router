import type { BranchTurn } from "../api/types";

interface MessageItemProps {
  turn: BranchTurn;
}

const selectionLabels = {
  AUTO_ROUTE: "自动路由",
  AUTO_FALLBACK: "自动降级",
  USER_SELECTED: "用户指定",
};

export function MessageItem({ turn }: MessageItemProps) {
  return (
    <article className="turn">
      <div className="message user-message">
        <span className="message-role">你</span>
        <p>{turn.user_message.content}</p>
      </div>
      {turn.active_answer ? (
        <div className="message assistant-message">
          <div className="assistant-heading">
            <span className="message-role">助手</span>
            <span className="answer-meta">
              {turn.active_answer.display_name ?? turn.active_answer.model_key} · {selectionLabels[turn.active_answer.selection_mode]}
            </span>
          </div>
          <p>{turn.active_answer.content}</p>
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
