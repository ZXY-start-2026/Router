import type { ConversationListItem, BranchTurn, ModelOption } from "../api/types";
import type { ModelSelection } from "../hooks/useChat";
import { Composer } from "./Composer";
import { MessageItem } from "./MessageItem";

interface ChatPanelProps {
  conversation: ConversationListItem | null;
  messages: BranchTurn[];
  models: ModelOption[];
  loading: boolean;
  submitting: boolean;
  error: string | null;
  onSend: (content: string, selection: ModelSelection) => Promise<unknown>;
}

export function ChatPanel({
  conversation,
  messages,
  models,
  loading,
  submitting,
  error,
  onSend,
}: ChatPanelProps) {
  if (!conversation) {
    return (
      <section className="welcome-panel">
        <span className="welcome-mark">M</span>
        <p className="eyebrow">MULTI-MODEL CHAT</p>
        <h2>从一个问题开始</h2>
        <p>在左侧创建会话。迭代1使用明确启用的 Mock Provider 验证聊天主流程。</p>
      </section>
    );
  }

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div>
          <span className="eyebrow">CURRENT CONVERSATION</span>
          <h2>{conversation.title}</h2>
        </div>
        <span className={`header-status status-${conversation.generation_status.toLowerCase()}`}>
          {submitting ? "生成中" : "已连接"}
        </span>
      </header>
      <div className="message-scroll" aria-live="polite">
        {loading && <p className="loading-line">正在加载消息…</p>}
        {!loading && !messages.length && (
          <div className="chat-empty">
            <span>01</span>
            <p>写下第一条消息，会话标题会自动生成。</p>
          </div>
        )}
        {messages.map((turn) => (
          <MessageItem key={turn.user_message.id} turn={turn} />
        ))}
      </div>
      {error && <p className="chat-error">{error}</p>}
      <Composer models={models} disabled={submitting} onSubmit={onSend} />
    </section>
  );
}

