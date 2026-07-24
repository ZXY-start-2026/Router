export type TitleSource = "DEFAULT" | "AUTO_FIRST_MESSAGE" | "USER_EDIT";
export type GenerationStatus =
  | "IDLE"
  | "PREPARING_CONTEXT"
  | "SEARCHING"
  | "ROUTING"
  | "GENERATING"
  | "SUCCEEDED"
  | "FAILED";
export type SelectionMode = "AUTO_ROUTE" | "USER_SELECTED";
export type RegenerationMode =
  | "REGENERATE_ORIGINAL_MODEL"
  | "REGENERATE_AUTO_ROUTE"
  | "REGENERATE_USER_SELECTED";
export type BranchPointType =
  | "ROOT"
  | "USER_MESSAGE_EDIT"
  | "ANSWER_VERSION_ACTIVATE";
export type AnswerStatus =
  | "GENERATING"
  | "SUCCEEDED_ACTIVE"
  | "SUCCEEDED_INACTIVE"
  | "FAILED"
  | "STOPPED";

export interface Conversation {
  id: string;
  title: string;
  title_source: TitleSource;
  active_branch_id: string;
  created_at: string;
  updated_at: string;
  generation_status: GenerationStatus;
}

export interface ConversationListItem {
  id: string;
  title: string;
  latest_message_preview: string | null;
  updated_at: string;
  generation_status: GenerationStatus;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface UserMessage {
  id: string;
  content: string;
  status: "PENDING" | "HAS_ACTIVE_ANSWER" | "GENERATION_FAILED";
  logical_position: number;
  created_at: string;
}

export interface Answer {
  id: string;
  content: string;
  model_key: string;
  model_id: string;
  display_name?: string;
  selection_mode: "AUTO_ROUTE" | "AUTO_FALLBACK" | "USER_SELECTED";
  status: AnswerStatus;
  created_at: string;
  completed_at: string;
  predicted_input_tokens?: number | null;
  predicted_output_tokens?: number | null;
  actual_input_tokens?: number | null;
  actual_output_tokens?: number | null;
  predicted_cost?: string | null;
  actual_cost?: string | null;
  price_version?: string | null;
  finish_reason?: string | null;
}

export interface BranchTurn {
  user_message: UserMessage;
  active_answer: Answer | null;
}

export interface BranchMessages {
  conversation_id: string;
  branch_id: string;
  items: BranchTurn[];
}

export interface Branch {
  id: string;
  parent_branch_id: string | null;
  branch_point_type: BranchPointType;
  branch_point_message_id: string | null;
  branch_point_answer_version_id: string | null;
  complete_turn_count: number;
  created_at: string;
  is_active: boolean;
}

export interface BranchList {
  conversation_id: string;
  active_branch_id: string;
  items: Branch[];
}

export interface AnswerVersions {
  user_message_id: string;
  branch_id: string;
  active_answer_version_id: string | null;
  items: Answer[];
}

export interface SendMessageRequest {
  content: string;
  selection_mode: SelectionMode;
  model_key: string | null;
}

export interface SendMessageResponse {
  user_message: UserMessage;
  active_answer: Answer | null;
  generation: {
    status: GenerationStatus;
    task_id?: string | null;
    search_status?: string | null;
    selected_model_key?: string | null;
    route_snapshot_id?: string | null;
    failure_code: string | null;
    failure_message: string | null;
  };
}

export interface GenerationOperationResponse extends SendMessageResponse {
  conversation_id: string;
  branch_id: string;
  created_branch_id: string | null;
}

export interface AnswerActivationResponse {
  conversation_id: string;
  branch_id: string;
  created_branch_id: string | null;
  active_answer: Answer;
}

export interface BranchActivationResponse {
  conversation_id: string;
  active_branch_id: string;
}

export interface ModelOption {
  model_key: string;
  label: string;
  available: boolean;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
  detail?: unknown;
}

export type MemoryVersionType =
  | "INITIAL_SYSTEM_SUMMARY"
  | "INCREMENTAL_SYSTEM_UPDATE"
  | "USER_EDIT"
  | "RESTORE"
  | "BRANCH_INHERIT";

export interface MemoryVersion {
  id: string;
  branch_id: string;
  version_number: number;
  type: MemoryVersionType;
  base_version_id: string | null;
  restored_from_version_id: string | null;
  inherited_from_version_id: string | null;
  protected_user_text: string;
  system_summary: string;
  covered_through_position: number | null;
  added_from_position: number | null;
  added_through_position: number | null;
  conflict_metadata: {
    status?: "CLEAR" | "CONFLICT" | "UNKNOWN";
    checked_through_position?: number | null;
    items?: Array<{
      dialogue_position?: number | null;
      description?: string;
    }>;
  };
  created_at: string;
  is_current: boolean;
}

export interface MemoryUpdateStatus {
  id: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED";
  target_from_position: number;
  target_through_position: number;
  attempt_count: number;
  error_category: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  created_memory_version_id: string | null;
}

export interface CurrentMemory {
  branch_id: string;
  current: MemoryVersion | null;
  latest_update: MemoryUpdateStatus | null;
  config: { n: number; k: number; m: number };
}

export interface MemoryVersions {
  items: MemoryVersion[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface MemoryOperation {
  branch_id: string;
  operation_status: "SUCCEEDED" | "FAILED";
  current: MemoryVersion | null;
  created_version: MemoryVersion | null;
  latest_update: MemoryUpdateStatus | null;
}

export interface RoleContent {
  name: string;
  persona: string;
  background: string;
  domain: string;
  traits: string[];
  style: string;
  constraints_text: string;
  source_template_id?: string | null;
}

export interface RoleVersion extends RoleContent {
  id: string;
  conversation_id: string;
  version_number: number;
  source_template_id: string | null;
  created_at: string;
}

export interface CurrentRole {
  conversation_id: string;
  branch_id: string;
  active_role: RoleVersion | null;
}

export interface RoleTemplate extends Omit<RoleContent, "source_template_id"> {
  id: string;
  created_at: string;
}

export interface RoleTemplateList {
  items: RoleTemplate[];
}
