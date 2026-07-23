import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type { ConversationListItem } from "../api/types";

export function useConversations() {
  const [items, setItems] = useState<ConversationListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadFirstPage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await api.listConversations();
      setItems(page.items);
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "会话加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadFirstPage();
  }, [loadFirstPage]);

  const loadMore = useCallback(async () => {
    if (!hasMore || !nextCursor || loading) return;
    setLoading(true);
    try {
      const page = await api.listConversations(nextCursor);
      setItems((current) => {
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...page.items.filter((item) => !seen.has(item.id))];
      });
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "更多会话加载失败");
    } finally {
      setLoading(false);
    }
  }, [hasMore, loading, nextCursor]);

  const create = useCallback(async () => {
    setError(null);
    try {
      const conversation = await api.createConversation();
      const item: ConversationListItem = {
        id: conversation.id,
        title: conversation.title,
        latest_message_preview: null,
        updated_at: conversation.updated_at,
        generation_status: conversation.generation_status,
      };
      setItems((current) => [item, ...current.filter((entry) => entry.id !== item.id)]);
      return conversation;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "会话创建失败");
      throw caught;
    }
  }, []);

  const refresh = useCallback(async (conversationId: string) => {
    const page = await api.listConversations();
    const updated = page.items.find((item) => item.id === conversationId);
    if (!updated) return;
    setItems((current) => {
      return [updated, ...current.filter((item) => item.id !== conversationId)];
    });
  }, []);

  const remove = useCallback(async (conversationId: string) => {
    setError(null);
    try {
      await api.deleteConversation(conversationId);
      setItems((current) => current.filter((item) => item.id !== conversationId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "删除失败");
    }
  }, []);

  return { items, loading, error, hasMore, loadMore, create, refresh, remove, reload: loadFirstPage };
}
