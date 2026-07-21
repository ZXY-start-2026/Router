import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type {
  BranchTurn,
  ModelOption,
  SelectionMode,
  SendMessageResponse,
} from "../api/types";

export interface ModelSelection {
  selectionMode: SelectionMode;
  modelKey: string | null;
}

export function useChat(
  conversationId: string | null,
  onConversationChanged: (conversationId: string) => Promise<void>,
) {
  const [messages, setMessages] = useState<BranchTurn[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.getMessages(conversationId);
      setMessages(result.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "消息加载失败");
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    api.listModels().then(setModels).catch(() => setModels([]));
  }, []);

  const send = useCallback(
    async (content: string, selection: ModelSelection): Promise<SendMessageResponse> => {
      if (!conversationId) throw new Error("请先创建会话");
      setSubmitting(true);
      setError(null);
      try {
        const result = await api.sendMessage(conversationId, {
          content,
          selection_mode: selection.selectionMode,
          model_key: selection.modelKey,
        });
        await reload();
        await onConversationChanged(conversationId);
        if (result.generation.status === "FAILED") {
          setError(result.generation.failure_message ?? "本轮生成失败");
        }
        return result;
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "消息发送失败";
        setError(message);
        throw caught;
      } finally {
        setSubmitting(false);
      }
    },
    [conversationId, onConversationChanged, reload],
  );

  return { messages, models, loading, submitting, error, send, reload };
}

