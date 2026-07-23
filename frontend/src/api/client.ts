import type {
  ApiErrorBody,
  BranchMessages,
  Conversation,
  ConversationListItem,
  CursorPage,
  ModelOption,
  SendMessageRequest,
  SendMessageResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code = "HTTP_ERROR",
  ) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  const body = (await response.json().catch(() => ({}))) as T & ApiErrorBody;
  if (!response.ok) {
    const message = body.error?.message ?? "请求失败，请稍后重试";
    throw new ApiError(message, response.status, body.error?.code);
  }
  return body;
}

export const api = {
  createConversation(title?: string): Promise<Conversation> {
    return request("/conversations", {
      method: "POST",
      body: JSON.stringify(title ? { title } : {}),
    });
  },

  listConversations(cursor?: string): Promise<CursorPage<ConversationListItem>> {
    const params = new URLSearchParams({ limit: "20" });
    if (cursor) params.set("cursor", cursor);
    return request(`/conversations?${params.toString()}`);
  },

  getConversation(id: string): Promise<Conversation> {
    return request(`/conversations/${id}`);
  },

  renameConversation(id: string, title: string): Promise<Conversation> {
    return request(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
  },

  getMessages(conversationId: string): Promise<BranchMessages> {
    return request(`/conversations/${conversationId}/messages`);
  },

  sendMessage(
    conversationId: string,
    body: SendMessageRequest,
  ): Promise<SendMessageResponse> {
    return request(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  listModels(): Promise<ModelOption[]> {
    return request("/models");
  },

  deleteConversation(id: string): Promise<void> {
    return request(`/conversations/${id}`, { method: "DELETE" });
  },
};

