import { useState, type FormEvent } from "react";

import type { ModelOption } from "../api/types";
import type { ModelSelection } from "../hooks/useChat";

interface MessageEditorProps {
  initialContent: string;
  models: ModelOption[];
  disabled: boolean;
  onCancel: () => void;
  onSubmit: (content: string, selection: ModelSelection) => Promise<unknown>;
}

export function MessageEditor({
  initialContent,
  models,
  disabled,
  onCancel,
  onSubmit,
}: MessageEditorProps) {
  const [content, setContent] = useState(initialContent);
  const [modelKey, setModelKey] = useState("AUTO_ROUTE");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const normalized = content.trim();
    if (!normalized || disabled) return;
    const selection: ModelSelection =
      modelKey === "AUTO_ROUTE"
        ? { selectionMode: "AUTO_ROUTE", modelKey: null }
        : { selectionMode: "USER_SELECTED", modelKey };
    try {
      await onSubmit(normalized, selection);
    } catch {
      // 错误由 useChat 展示；保留编辑内容，便于用户修改后重试。
    }
  };

  return (
    <form className="message-editor" onSubmit={(event) => void submit(event)}>
      <textarea
        aria-label="编辑消息内容"
        value={content}
        disabled={disabled}
        rows={4}
        onChange={(event) => setContent(event.target.value)}
      />
      <div className="message-editor-actions">
        <select
          aria-label="修改后使用的模型"
          value={modelKey}
          disabled={disabled}
          onChange={(event) => setModelKey(event.target.value)}
        >
          <option value="AUTO_ROUTE">自动路由</option>
          {models.map((model) => (
            <option
              key={model.model_key}
              value={model.model_key}
              disabled={!model.available}
            >
              仅本条使用 {model.label}
            </option>
          ))}
        </select>
        <span className="editor-branch-note">保存后将创建新分支</span>
        <button type="button" disabled={disabled} onClick={onCancel}>
          取消
        </button>
        <button type="submit" disabled={disabled || !content.trim()}>
          {disabled ? "生成中…" : "创建分支并生成"}
        </button>
      </div>
    </form>
  );
}
