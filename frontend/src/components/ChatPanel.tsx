import type {
  AnswerVersions,
  Branch,
  BranchTurn,
  ConversationListItem,
  CurrentMemory,
  CurrentRole,
  MemoryVersions,
  ModelOption,
  RegenerationMode,
  RoleContent,
  RoleTemplate,
} from "../api/types";
import { useState } from "react";
import type { ModelSelection } from "../hooks/useChat";
import { BranchSwitcher } from "./BranchSwitcher";
import { Composer } from "./Composer";
import { MessageItem } from "./MessageItem";
import { MemoryPanel } from "./MemoryPanel";
import { RolePanel } from "./RolePanel";
import { SideDrawer } from "./SideDrawer";
import "./chat-actions.css";
import "./panels.css";

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
  memory?: CurrentMemory | null;
  memoryVersions?: MemoryVersions | null;
  currentRole?: CurrentRole | null;
  roleTemplates?: RoleTemplate[];
  onLoadMemoryVersions?: () => Promise<unknown>;
  onSaveMemory?: (text: string) => Promise<unknown>;
  onRestoreMemory?: (versionId: string) => Promise<unknown>;
  onLoadRoleTemplates?: () => Promise<unknown>;
  onSaveRole?: (content: RoleContent) => Promise<unknown>;
  onDeactivateRole?: () => Promise<unknown>;
  onCreateRoleTemplate?: (
    content: Omit<RoleContent, "source_template_id">,
  ) => Promise<unknown>;
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
  memory = null,
  memoryVersions = null,
  currentRole = null,
  roleTemplates = [],
  onLoadMemoryVersions = noOp,
  onSaveMemory = noOp,
  onRestoreMemory = noOp,
  onLoadRoleTemplates = noOp,
  onSaveRole = noOp,
  onDeactivateRole = noOp,
  onCreateRoleTemplate = noOp,
}: ChatPanelProps) {
  const [drawer, setDrawer] = useState<"memory" | "role" | null>(null);

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
        <div className="chat-header-inner">
          <div>
            <span className="eyebrow">CURRENT CONVERSATION</span>
            <h2>{conversation.title}</h2>
          </div>
          <div className="chat-header-controls">
            <div className="chat-feature-actions" aria-label="会话设置">
              <button type="button" onClick={() => setDrawer("memory")}>
                备忘录
              </button>
              <button
                type="button"
                onClick={() => {
                  setDrawer("role");
                  void onLoadRoleTemplates().catch(() => undefined);
                }}
              >
                角色
              </button>
            </div>
            <span
              className={`header-status status-${conversation.generation_status.toLowerCase()}`}
            >
              {submitting ? "处理中" : "已连接"}
            </span>
          </div>
        </div>
      </header>
      {branches.length > 1 && activeBranchId ? (
        <section className="chat-branch-toolbar" aria-label="会话分支">
          <div className="chat-branch-toolbar-inner">
            <BranchSwitcher
              branches={branches}
              activeId={activeBranchId}
              disabled={submitting}
              onActivate={onSwitchBranch}
            />
          </div>
        </section>
      ) : null}
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
      <SideDrawer
        open={drawer === "memory"}
        title="会话备忘录"
        onClose={() => setDrawer(null)}
      >
        <MemoryPanel
          memory={memory}
          versions={memoryVersions}
          disabled={submitting}
          onLoadVersions={onLoadMemoryVersions}
          onSave={onSaveMemory}
          onRestore={onRestoreMemory}
        />
      </SideDrawer>
      <SideDrawer
        open={drawer === "role"}
        title="助手角色"
        onClose={() => setDrawer(null)}
      >
        <RolePanel
          role={currentRole}
          templates={roleTemplates}
          disabled={submitting}
          onLoadTemplates={onLoadRoleTemplates}
          onSave={onSaveRole}
          onDeactivate={onDeactivateRole}
          onCreateTemplate={onCreateRoleTemplate}
        />
      </SideDrawer>
    </section>
  );
}
