import type {
  AnswerVersions,
  Branch,
  BranchTurn,
  ConversationListItem,
  ModelOption,
  RegenerationMode,
} from "../api/types";
import type { ModelSelection } from "../hooks/useChat";
import { BranchSwitcher } from "./BranchSwitcher";
import { Composer } from "./Composer";
import { MessageItem } from "./MessageItem";
import "./chat-actions.css";

interface ChatPanelProps {
  conversation: ConversationListItem | null;
  messages: BranchTurn[];
  models: ModelOption[];
  loading: boolean;
  submitting: boolean;
  error: string | null;
  onSend: (content: string, selection: ModelSelection) => Promise<unknown>;
  branches?: Branch[];
  activeBranchId?: string | null;
  answerVersions?: Record<string, AnswerVersions>;
  onLoadVersions?: (messageId: string) => Promise<unknown>;
  onRegenerate?: (
    messageId: string,
    mode: RegenerationMode,
    modelKey: string | null,
  ) => Promise<unknown>;
  onActivateAnswer?: (messageId: string, answerId: string) => Promise<unknown>;
  onEditMessage?: (
    messageId: string,
    content: string,
    selection: ModelSelection,
  ) => Promise<unknown>;
  onSwitchBranch?: (branchId: string) => Promise<unknown>;
}

const noOp = async () => undefined;

export function ChatPanel({
  conversation,
  messages,
  models,
  loading,
  submitting,
  error,
  onSend,
  branches = [],
  activeBranchId = null,
  answerVersions = {},
  onLoadVersions = noOp,
  onRegenerate = noOp,
  onActivateAnswer = noOp,
  onEditMessage = noOp,
  onSwitchBranch = noOp,
}: ChatPanelProps) {
  if (!conversation) {
    return (
      <section className="welcome-panel">
        <span className="welcome-mark">M</span>
        <p className="eyebrow">MULTI-MODEL CHAT</p>
        <h2>从一个问题开始</h2>
        <p>在左侧创建会话，系统会根据配置选择合适的模型回答。</p>
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
        <div className="chat-header-actions">
          <BranchSwitcher
            branches={branches}
            activeId={activeBranchId}
            disabled={submitting}
            onActivate={onSwitchBranch}
          />
          <span
            className={`header-status status-${conversation.generation_status.toLowerCase()}`}
          >
            {submitting ? "处理中" : "已连接"}
          </span>
        </div>
      </header>
      <div className="message-scroll" aria-live="polite">
        {loading && <p className="loading-line">正在加载消息…</p>}
        {!loading && !messages.length && (
          <div className="chat-empty">
            <span>01</span>
            <p>写下第一条消息，会话标题会自动生成。</p>
          </div>
        )}
        {messages.map((turn, index) => (
          <MessageItem
            key={turn.user_message.id}
            turn={turn}
            models={models}
            disabled={submitting}
            hasLaterMessages={index < messages.length - 1}
            versions={answerVersions[turn.user_message.id] ?? null}
            onLoadVersions={onLoadVersions}
            onRegenerate={onRegenerate}
            onActivateAnswer={onActivateAnswer}
            onEditMessage={onEditMessage}
          />
        ))}
      </div>
      {error && <p className="chat-error">{error}</p>}
      <Composer models={models} disabled={submitting} onSubmit={onSend} />
    </section>
  );
}
