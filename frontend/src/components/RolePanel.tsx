import { useEffect, useState } from "react";

import type {
  CurrentRole,
  RoleContent,
  RoleTemplate,
} from "../api/types";
import { ConfirmationDialog } from "./ConfirmationDialog";

interface RolePanelProps {
  role: CurrentRole | null;
  templates: RoleTemplate[];
  disabled: boolean;
  onLoadTemplates: () => Promise<unknown>;
  onSave: (content: RoleContent) => Promise<unknown>;
  onDeactivate: () => Promise<unknown>;
  onCreateTemplate: (
    content: Omit<RoleContent, "source_template_id">,
  ) => Promise<unknown>;
}

const emptyRole: RoleContent = {
  name: "",
  persona: "",
  background: "",
  domain: "",
  traits: [],
  style: "",
  constraints_text: "",
  source_template_id: null,
};

export function RolePanel({
  role,
  templates,
  disabled,
  onLoadTemplates,
  onSave,
  onDeactivate,
  onCreateTemplate,
}: RolePanelProps) {
  const [form, setForm] = useState<RoleContent>(emptyRole);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);

  useEffect(() => {
    const current = role?.active_role;
    setForm(
      current
        ? {
            name: current.name,
            persona: current.persona,
            background: current.background,
            domain: current.domain,
            traits: current.traits,
            style: current.style,
            constraints_text: current.constraints_text,
            source_template_id: current.source_template_id,
          }
        : emptyRole,
    );
  }, [role?.active_role?.id]);

  const update = (
    field: keyof RoleContent,
    value: string | string[] | null,
  ) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const templateContent = () => ({
    name: form.name,
    persona: form.persona,
    background: form.background,
    domain: form.domain,
    traits: form.traits,
    style: form.style,
    constraints_text: form.constraints_text,
  });

  return (
    <div className="settings-panel">
      <div className="panel-summary-row">
        <span>
          {role?.active_role
            ? `当前版本 ${role.active_role.version_number}`
            : "当前未设置角色"}
        </span>
        <span>仅影响当前分支后续消息</span>
      </div>

      <label className="panel-field">
        <span>从模板填充</span>
        <select
          value={form.source_template_id ?? ""}
          disabled={disabled}
          onFocus={() => void onLoadTemplates().catch(() => undefined)}
          onChange={(event) => {
            const template = templates.find(
              (item) => item.id === event.target.value,
            );
            if (!template) {
              update("source_template_id", null);
              return;
            }
            setForm({
              name: template.name,
              persona: template.persona,
              background: template.background,
              domain: template.domain,
              traits: template.traits,
              style: template.style,
              constraints_text: template.constraints_text,
              source_template_id: template.id,
            });
          }}
        >
          <option value="">不使用模板</option>
          {templates.map((template) => (
            <option key={template.id} value={template.id}>
              {template.name}
            </option>
          ))}
        </select>
      </label>

      <label className="panel-field">
        <span>角色名称</span>
        <input
          value={form.name}
          disabled={disabled}
          onChange={(event) => update("name", event.target.value)}
        />
      </label>
      <label className="panel-field">
        <span>人格定位</span>
        <textarea
          rows={3}
          value={form.persona}
          disabled={disabled}
          onChange={(event) => update("persona", event.target.value)}
        />
      </label>
      <label className="panel-field">
        <span>背景</span>
        <textarea
          rows={3}
          value={form.background}
          disabled={disabled}
          onChange={(event) => update("background", event.target.value)}
        />
      </label>
      <label className="panel-field">
        <span>专业领域</span>
        <input
          value={form.domain}
          disabled={disabled}
          onChange={(event) => update("domain", event.target.value)}
        />
      </label>
      <label className="panel-field">
        <span>性格特征（每行一个）</span>
        <textarea
          rows={3}
          value={form.traits.join("\n")}
          disabled={disabled}
          onChange={(event) =>
            update("traits", event.target.value.split("\n"))
          }
        />
      </label>
      <label className="panel-field">
        <span>表达风格</span>
        <textarea
          rows={3}
          value={form.style}
          disabled={disabled}
          onChange={(event) => update("style", event.target.value)}
        />
      </label>
      <label className="panel-field">
        <span>回答约束</span>
        <textarea
          rows={4}
          value={form.constraints_text}
          disabled={disabled}
          onChange={(event) => update("constraints_text", event.target.value)}
        />
      </label>

      <div className="panel-action-row">
        <button
          className="panel-primary-button"
          type="button"
          disabled={disabled || !form.name.trim()}
          onClick={() => void onSave(form).catch(() => undefined)}
        >
          保存角色
        </button>
        <button
          type="button"
          disabled={disabled || !form.name.trim()}
          onClick={() =>
            void onCreateTemplate(templateContent()).catch(() => undefined)
          }
        >
          保存为模板
        </button>
        <button
          className="panel-danger-button"
          type="button"
          disabled={disabled || !role?.active_role}
          onClick={() => setConfirmDeactivate(true)}
        >
          停用角色
        </button>
      </div>

      {confirmDeactivate ? (
        <ConfirmationDialog
          title="停用当前角色？"
          description="只会清空当前分支的角色指针，旧版本和历史消息不会被删除。"
          confirmLabel="确认停用"
          onCancel={() => setConfirmDeactivate(false)}
          onConfirm={() => {
            setConfirmDeactivate(false);
            void onDeactivate().catch(() => undefined);
          }}
        />
      ) : null}
    </div>
  );
}
