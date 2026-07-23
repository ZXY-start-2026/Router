import { useEffect, useState } from "react";

import type { ModelOption, RegenerationMode } from "../api/types";

interface MessageActionsProps {
  hasActiveAnswer: boolean;
  models: ModelOption[];
  disabled: boolean;
  onRegenerate: (
    mode: RegenerationMode,
    modelKey: string | null,
  ) => Promise<unknown>;
  onShowVersions: () => void;
}

export function MessageActions({
  hasActiveAnswer,
  models,
  disabled,
  onRegenerate,
  onShowVersions,
}: MessageActionsProps) {
  const [modelKey, setModelKey] = useState(
    models.find((model) => model.available)?.model_key ?? "",
  );

  useEffect(() => {
    const isAvailable = models.some(
      (model) => model.model_key === modelKey && model.available,
    );
    if (!isAvailable) {
      setModelKey(models.find((model) => model.available)?.model_key ?? "");
    }
  }, [modelKey, models]);

  const run = (mode: RegenerationMode, selected: string | null = null) => {
    void onRegenerate(mode, selected).catch(() => undefined);
  };

  return (
    <details className="message-actions">
      <summary>回答操作</summary>
      <div className="message-actions-menu">
        <button
          type="button"
          disabled={disabled || !hasActiveAnswer}
          onClick={() => run("REGENERATE_ORIGINAL_MODEL")}
        >
          使用原模型重新生成
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => run("REGENERATE_AUTO_ROUTE")}
        >
          重新自动路由
        </button>
        <div className="regenerate-model-row">
          <select
            aria-label="重新生成使用的模型"
            value={modelKey}
            disabled={disabled}
            onChange={(event) => setModelKey(event.target.value)}
          >
            {models.map((model) => (
              <option
                key={model.model_key}
                value={model.model_key}
                disabled={!model.available}
              >
                {model.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={disabled || !modelKey}
            onClick={() => run("REGENERATE_USER_SELECTED", modelKey)}
          >
            指定模型重新生成
          </button>
        </div>
        <button type="button" disabled={disabled} onClick={onShowVersions}>
          查看历史版本
        </button>
      </div>
    </details>
  );
}
