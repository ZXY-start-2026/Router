import {
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import type { ModelOption, SelectionMode } from "../api/types";
import type { ModelSelection } from "../hooks/useChat";

interface ComposerProps {
  models: ModelOption[];
  disabled: boolean;
  onSubmit: (content: string, selection: ModelSelection) => Promise<unknown>;
}

export function Composer({ models, disabled, onSubmit }: ComposerProps) {
  const [content, setContent] = useState("");
  const [selected, setSelected] = useState("AUTO_ROUTE");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const normalized = content.trim();
    if (!normalized || disabled) return;
    const selection: ModelSelection =
      selected === "AUTO_ROUTE"
        ? { selectionMode: "AUTO_ROUTE", modelKey: null }
        : { selectionMode: "USER_SELECTED" as SelectionMode, modelKey: selected };
    try {
      await onSubmit(normalized, selection);
      setContent("");
    } catch {
      // 父级 Hook 已展示错误；保留正文供用户重试。
    } finally {
      setSelected("AUTO_ROUTE");
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.nativeEvent.isComposing
    ) {
      return;
    }
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  };

  return (
    <form className="composer" onSubmit={(event) => void handleSubmit(event)}>
      <textarea
        aria-label="消息内容"
        placeholder="输入消息…"
        rows={3}
        value={content}
        disabled={disabled}
        onChange={(event) => setContent(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className="composer-actions">
        <label>
          <span className="sr-only">本条消息使用的模型</span>
          <select
            aria-label="本条消息使用的模型"
            value={selected}
            disabled={disabled}
            onChange={(event) => setSelected(event.target.value)}
          >
            <option value="AUTO_ROUTE">自动路由</option>
            {models.map((model) => (
              <option key={model.model_key} value={model.model_key} disabled={!model.available}>
                仅本条使用 {model.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={disabled || !content.trim()}>
          {disabled ? "生成中…" : "发送"}
        </button>
      </div>
    </form>
  );
}
