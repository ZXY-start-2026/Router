import type {
  ApiErrorBody,
  AnswerActivationResponse,
  AnswerVersions,
  BranchActivationResponse,
  BranchList,
  BranchMessages,
  Conversation,
  ConversationListItem,
  CurrentMemory,
  CurrentRole,
  CursorPage,
  GenerationOperationResponse,
  MemoryOperation,
  MemoryVersions,
  ModelOption,
  RegenerationMode,
  RoleContent,
  RoleTemplate,
  RoleTemplateList,
  SendMessageRequest,
  SendMessageResponse,
  SelectionMode,
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

  listAnswerVersions(messageId: string, branchId: string): Promise<AnswerVersions> {
    const params = new URLSearchParams({ branch_id: branchId });
    return request(`/messages/${messageId}/answers?${params.toString()}`);
  },

  regenerateAnswer(
    messageId: string,
    body: {
      branch_id: string;
      mode: RegenerationMode;
      model_key: string | null;
    },
  ): Promise<GenerationOperationResponse> {
    return request(`/messages/${messageId}/regenerations`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  activateAnswer(
    messageId: string,
    answerId: string,
    branchId: string,
  ): Promise<AnswerActivationResponse> {
    return request(`/messages/${messageId}/answers/${answerId}/activate`, {
      method: "POST",
      body: JSON.stringify({ branch_id: branchId }),
    });
  },

  editMessage(
    messageId: string,
    body: {
      branch_id: string;
      content: string;
      selection_mode: SelectionMode;
      model_key: string | null;
    },
  ): Promise<GenerationOperationResponse> {
    return request(`/messages/${messageId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  listBranches(conversationId: string): Promise<BranchList> {
    return request(`/conversations/${conversationId}/branches`);
  },

  activateBranch(
    conversationId: string,
    branchId: string,
  ): Promise<BranchActivationResponse> {
    return request(`/conversations/${conversationId}/branches/${branchId}/activate`, {
      method: "POST",
    });
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

  getMemory(branchId: string): Promise<CurrentMemory> {
    return request(`/branches/${branchId}/memory`);
  },

  listMemoryVersions(
    branchId: string,
    cursor?: string,
  ): Promise<MemoryVersions> {
    const params = new URLSearchParams({ limit: "20" });
    if (cursor) params.set("cursor", cursor);
    return request(`/branches/${branchId}/memory/versions?${params.toString()}`);
  },

  updateMemory(
    branchId: string,
    protectedUserText: string,
  ): Promise<MemoryOperation> {
    return request(`/branches/${branchId}/memory`, {
      method: "PUT",
      body: JSON.stringify({ protected_user_text: protectedUserText }),
    });
  },

  restoreMemory(branchId: string, versionId: string): Promise<MemoryOperation> {
    return request(`/branches/${branchId}/memory/versions/${versionId}/restore`, {
      method: "POST",
    });
  },

  getRole(conversationId: string): Promise<CurrentRole> {
    return request(`/conversations/${conversationId}/role`);
  },

  updateRole(conversationId: string, content: RoleContent): Promise<CurrentRole> {
    return request(`/conversations/${conversationId}/role`, {
      method: "PUT",
      body: JSON.stringify(content),
    });
  },

  deactivateRole(conversationId: string): Promise<CurrentRole> {
    return request(`/conversations/${conversationId}/role/deactivate`, {
      method: "POST",
    });
  },

  listRoleTemplates(): Promise<RoleTemplateList> {
    return request("/role-templates");
  },

  createRoleTemplate(
    content: Omit<RoleContent, "source_template_id">,
  ): Promise<RoleTemplate> {
    return request("/role-templates", {
      method: "POST",
      body: JSON.stringify(content),
    });
  },

  deleteConversation(id: string): Promise<void> {
    return request(`/conversations/${id}`, { method: "DELETE" });
  },
};
