import { useCallback, useMemo, useState } from "react";

import { AppLayout } from "./components/AppLayout";
import { ChatPanel } from "./components/ChatPanel";
import { ConversationList } from "./components/ConversationList";
import { useChat } from "./hooks/useChat";
import { useConversations } from "./hooks/useConversations";

export default function App() {
  const conversations = useConversations();
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const refreshConversation = useCallback(
    (id: string) => conversations.refresh(id),
    [conversations.refresh],
  );
  const chat = useChat(currentId, refreshConversation);
  const currentConversation = useMemo(
    () => conversations.items.find((item) => item.id === currentId) ?? null,
    [conversations.items, currentId],
  );

  const createConversation = async () => {
    try {
      const created = await conversations.create();
      setCurrentId(created.id);
      setSidebarOpen(false);
    } catch {
      // useConversations 负责显示请求错误。
    }
  };

  const selectConversation = (id: string) => {
    setCurrentId(id);
    setSidebarOpen(false);
  };

  return (
    <AppLayout
      sidebarOpen={sidebarOpen}
      onToggleSidebar={() => setSidebarOpen((open) => !open)}
      sidebar={
        <ConversationList
          items={conversations.items}
          currentId={currentId}
          loading={conversations.loading}
          hasMore={conversations.hasMore}
          error={conversations.error}
          onSelect={selectConversation}
          onCreate={() => void createConversation()}
          onLoadMore={() => void conversations.loadMore()}
        />
      }
      main={
        <ChatPanel
          conversation={currentConversation}
          messages={chat.messages}
          models={chat.models}
          loading={chat.loading}
          submitting={chat.submitting}
          error={chat.error}
          onSend={chat.send}
        />
      }
    />
  );
}
