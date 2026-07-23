import { useState, type UIEvent } from "react";

import type { ConversationListItem } from "../api/types";
import { ConfirmationDialog } from "./ConfirmationDialog";
import "./conversation-list.css";

interface ConversationListProps {
  items: ConversationListItem[];
  currentId: string | null;
  loading: boolean;
  hasMore: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onCreate: () => void;
  onLoadMore: () => void;
}

const statusLabels: Record<ConversationListItem["generation_status"], string> = {
  IDLE: "待开始",
  PREPARING_CONTEXT: "准备上下文",
  SEARCHING: "搜索中",
  ROUTING: "路由中",
  GENERATING: "生成中",
  SUCCEEDED: "已完成",
  FAILED: "生成失败",
};

export function ConversationList({
  items,
  currentId,
  loading,
  hasMore,
  error,
  onSelect,
  onDelete,
  onCreate,
  onLoadMore,
}: ConversationListProps) {
  const [pendingDelete, setPendingDelete] = useState<ConversationListItem | null>(null);

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    const element = event.currentTarget;
    if (hasMore && !loading && element.scrollHeight - element.scrollTop - element.clientHeight < 80) {
      onLoadMore();
    }
  };

  return (
    <section className="conversation-list">
      <div className="brand-row">
        <div>
          <span className="eyebrow">LOCAL WORKSPACE</span>
          <h1>多模型聊天</h1>
        </div>
        <button className="new-chat-button" type="button" onClick={onCreate}>
          新建
        </button>
      </div>
      {error && <p className="inline-error">{error}</p>}
      <div className="conversation-scroll" onScroll={handleScroll}>
        {items.map((item) => (
          <div className="conversation-row" key={item.id}>
            <button
              className={`conversation-card ${item.id === currentId ? "active" : ""}`}
              type="button"
              aria-label={`打开会话“${item.title}”`}
              aria-current={item.id === currentId ? "true" : undefined}
              onClick={() => onSelect(item.id)}
            >
              <span className="conversation-title">{item.title}</span>
              <span className="conversation-preview">
                {item.latest_message_preview ?? "尚无消息"}
              </span>
              <span className="conversation-meta">
                <time dateTime={item.updated_at}>
                  {new Date(item.updated_at).toLocaleString("zh-CN", {
                    month: "numeric",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
                <span className={`status-dot status-${item.generation_status.toLowerCase()}`}>
                  {statusLabels[item.generation_status]}
                </span>
              </span>
            </button>
            <button
              className="conversation-delete-button"
              type="button"
              aria-label={`删除会话“${item.title}”`}
              title="删除会话"
              onClick={() => setPendingDelete(item)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5" />
              </svg>
            </button>
          </div>
        ))}
        {!items.length && !loading && <p className="empty-list">创建一个会话开始聊天</p>}
        {loading && <p className="loading-line">正在加载…</p>}
      </div>
      {pendingDelete && (
        <ConfirmationDialog
          title="删除会话？"
          description="删除后将不再显示该会话，后端数据仍会保留。是否继续？"
          confirmLabel="确认删除"
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => {
            onDelete(pendingDelete.id);
            setPendingDelete(null);
          }}
        />
      )}
    </section>
  );
}
