export type TaskStatus = 'queued' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed'

export interface SessionSummary {
  id: string
  title: string
  status: string
  created_at: string
  updated_at: string
  last_message?: string | null
}

export interface ChartPoint {
  label: string
  value: number
}

export interface ChartSpec {
  id: string
  title: string
  unit?: string
  points: ChartPoint[]
}

export interface MessageRecord {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
  metadata: {
    task_id?: string
    duration_seconds?: number
    warnings?: string[]
    charts?: ChartSpec[]
    [key: string]: unknown
  }
}

export interface IntentStock {
  name?: string | null
  code?: string | null
  market?: string | null
}

export interface IntentAnalysis {
  task_type: string
  stocks: IntentStock[]
  dimensions: string[]
  time_range?: string | null
  parameters: Record<string, unknown>
  suggested_route: 'direct_tool' | 'specialist_agent' | 'multi_agent'
  execution_route: 'direct_tool' | 'legacy_workflow' | 'none'
  confidence: number
  summary: string
  source: 'llm' | 'deterministic_direct' | 'deterministic_fallback'
  fallback_reason?: string | null
  utterance_intent?: string
  intent_change?: 'new' | 'continue' | 'refine' | 'switch' | 'cancel' | 'resume'
  requires_clarification?: boolean
  clarification_question?: string | null
  active_task_id?: string | null
  dialogue_state_version?: number
  resolved_query?: string
  selected_agents?: string[]
  state_patch?: Record<string, unknown>
}

export interface TaskRecord {
  id: string
  session_id: string
  query: string
  status: TaskStatus
  architecture: string
  intent?: IntentAnalysis | null
  execution_id?: string | null
  report?: string | null
  report_path?: string | null
  error?: string | null
  warnings: string[]
  duration_seconds?: number | null
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  cancel_requested_at?: string | null
  cancelled_at?: string | null
  cancel_reason?: string | null
}

export interface SessionDetail extends SessionSummary {
  messages: MessageRecord[]
  tasks: TaskRecord[]
}

export interface ChatAccepted {
  task_id: string
  session_id: string
  status: TaskStatus
  events_url: string
  reused: boolean
}

export interface ExecutionEvent {
  id: number
  type: string
  created_at: string
  payload: Record<string, unknown>
}

export type AgentStatus = 'waiting' | 'running' | 'completed' | 'failed' | 'cancelled'
