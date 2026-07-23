import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type {
  AnswerVersions,
  Branch,
  BranchTurn,
  ModelOption,
  RegenerationMode,
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
  const [branches, setBranches] = useState<Branch[]>([]);
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [answerVersions, setAnswerVersions] = useState<Record<string, AnswerVersions>>({});
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!conversationId) {
      setMessages([]);
      setBranches([]);
      setActiveBranchId(null);
      setAnswerVersions({});
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [messageResult, branchResult] = await Promise.all([
        api.getMessages(conversationId),
        api.listBranches(conversationId),
      ]);
      setMessages(messageResult.items);
      setBranches(branchResult.items);
      setActiveBranchId(branchResult.active_branch_id);
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

  const refreshAfterAction = useCallback(async () => {
    setAnswerVersions({});
    await reload();
    if (conversationId) await onConversationChanged(conversationId);
  }, [conversationId, onConversationChanged, reload]);

  const runAction = useCallback(
    async <T,>(action: () => Promise<T>): Promise<T> => {
      if (submitting) throw new Error("已有操作正在进行");
      setSubmitting(true);
      setError(null);
      try {
        const result = await action();
        await refreshAfterAction();
        return result;
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "操作失败";
        setError(message);
        throw caught;
      } finally {
        setSubmitting(false);
      }
    },
    [refreshAfterAction, submitting],
  );

  const send = useCallback(
    async (content: string, selection: ModelSelection): Promise<SendMessageResponse> => {
      if (!conversationId) throw new Error("请先创建会话");
      const result = await runAction(() =>
        api.sendMessage(conversationId, {
          content,
          selection_mode: selection.selectionMode,
          model_key: selection.modelKey,
        }),
      );
      if (result.generation.status === "FAILED") {
        setError(result.generation.failure_message ?? "本轮生成失败");
      }
      return result;
    },
    [conversationId, runAction],
  );

  const loadAnswerVersions = useCallback(
    async (messageId: string): Promise<AnswerVersions> => {
      const cached = answerVersions[messageId];
      if (cached) return cached;
      if (!activeBranchId) throw new Error("当前分支不存在");
      const result = await api.listAnswerVersions(messageId, activeBranchId);
      setAnswerVersions((current) => ({ ...current, [messageId]: result }));
      return result;
    },
    [activeBranchId, answerVersions],
  );

  const regenerate = useCallback(
    async (
      messageId: string,
      mode: RegenerationMode,
      modelKey: string | null,
    ) => {
      if (!activeBranchId) throw new Error("当前分支不存在");
      const result = await runAction(() =>
        api.regenerateAnswer(messageId, {
          branch_id: activeBranchId,
          mode,
          model_key: modelKey,
        }),
      );
      if (result.generation.status === "FAILED") {
        setError(result.generation.failure_message ?? "重新生成失败");
      }
      return result;
    },
    [activeBranchId, runAction],
  );

  const activateAnswer = useCallback(
    async (messageId: string, answerId: string) => {
      if (!activeBranchId) throw new Error("当前分支不存在");
      return runAction(() => api.activateAnswer(messageId, answerId, activeBranchId));
    },
    [activeBranchId, runAction],
  );

  const editMessage = useCallback(
    async (messageId: string, content: string, selection: ModelSelection) => {
      if (!activeBranchId) throw new Error("当前分支不存在");
      const result = await runAction(() =>
        api.editMessage(messageId, {
          branch_id: activeBranchId,
          content,
          selection_mode: selection.selectionMode,
          model_key: selection.modelKey,
        }),
      );
      if (result.generation.status === "FAILED") {
        setError(result.generation.failure_message ?? "修改后的消息生成失败");
      }
      return result;
    },
    [activeBranchId, runAction],
  );

  const switchBranch = useCallback(
    async (branchId: string) => {
      if (!conversationId || branchId === activeBranchId) return;
      await runAction(() => api.activateBranch(conversationId, branchId));
    },
    [activeBranchId, conversationId, runAction],
  );

  return {
    messages,
    models,
    branches,
    activeBranchId,
    answerVersions,
    loading,
    submitting,
    error,
    send,
    regenerate,
    activateAnswer,
    editMessage,
    switchBranch,
    loadAnswerVersions,
    reload,
  };
}
