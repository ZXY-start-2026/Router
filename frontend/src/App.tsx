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

  const deleteConversation = (id: string) => {
    conversations.hide(id);
    if (currentId === id) setCurrentId(null);
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
          onDelete={deleteConversation}
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
          branches={chat.branches}
          activeBranchId={chat.activeBranchId}
          answerVersions={chat.answerVersions}
          onLoadVersions={chat.loadAnswerVersions}
          onRegenerate={chat.regenerate}
          onActivateAnswer={chat.activateAnswer}
          onEditMessage={chat.editMessage}
          onSwitchBranch={chat.switchBranch}
          memory={chat.memory}
          memoryVersions={chat.memoryVersions}
          currentRole={chat.currentRole}
          roleTemplates={chat.roleTemplates}
          onLoadMemoryVersions={chat.loadMemoryVersions}
          onSaveMemory={chat.saveProtectedMemory}
          onRestoreMemory={chat.restoreMemory}
          onLoadRoleTemplates={chat.loadRoleTemplates}
          onSaveRole={chat.saveRole}
          onDeactivateRole={chat.deactivateRole}
          onCreateRoleTemplate={chat.createRoleTemplate}
        />
      }
    />
  );
}
