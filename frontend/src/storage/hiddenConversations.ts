export const HIDDEN_CONVERSATION_IDS_KEY = "multi-model-chat:hidden-conversation-ids";

function getLocalStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadHiddenConversationIds(): Set<string> {
  const storage = getLocalStorage();
  if (!storage) return new Set();

  try {
    const value: unknown = JSON.parse(storage.getItem(HIDDEN_CONVERSATION_IDS_KEY) ?? "[]");
    if (!Array.isArray(value)) return new Set();
    return new Set(value.filter((id): id is string => typeof id === "string"));
  } catch {
    return new Set();
  }
}

export function saveHiddenConversationIds(ids: ReadonlySet<string>): void {
  const storage = getLocalStorage();
  if (!storage) return;

  try {
    storage.setItem(HIDDEN_CONVERSATION_IDS_KEY, JSON.stringify([...ids]));
  } catch {
    // 本地存储不可用时仍保留当前页面内的隐藏状态。
  }
}
