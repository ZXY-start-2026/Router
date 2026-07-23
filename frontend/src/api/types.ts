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
