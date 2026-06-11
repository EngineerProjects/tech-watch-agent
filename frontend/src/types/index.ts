export const SessionStatus = {
  CREATED: 'created',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  PAUSED: 'paused',
  AWAITING_APPROVAL: 'awaiting_approval',
} as const;

export type SessionStatus = (typeof SessionStatus)[keyof typeof SessionStatus];

export const SessionPhase = {
  PLAN: 'plan',
  RESEARCH: 'research',
  COLLECTION: 'collection',
  ANALYSIS: 'analysis',
  SYNTHESIS: 'synthesis',
  DELIVERY: 'delivery',
  COMPLETED: 'completed',
} as const;

export type SessionPhase = (typeof SessionPhase)[keyof typeof SessionPhase];

export const StepStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  DONE: 'done',
  FAILED: 'failed',
  SKIPPED: 'skipped',
} as const;

export type StepStatus = (typeof StepStatus)[keyof typeof StepStatus];

export interface PlanStep {
  step_id: string;
  name: string;
  description: string;
  step_type: string;
  status: StepStatus;
  tool_name?: string;
  params?: Record<string, any>;
  result?: string;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

export interface Article {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  topic: string;
  published_date?: string;
  relevance_score?: number;
}

export interface ResearchSession {
  id: string;
  title?: string;
  subject?: string | null;
  research_instructions?: string | null;
  research_brief: string;
  status: SessionStatus;
  phase: SessionPhase;
  plan?: PlanStep[];
  plan_version: number;
  current_step_index?: number;
  research_results?: any[];
  analysis_results?: string;
  final_report?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  meta_data?: Record<string, any>;
  iterations_count?: number;
  has_checkpoint?: boolean;
  compaction_version?: number;
}

export interface NewsletterRun {
  id: string;
  subject?: string;
  status: string;
  articles_count?: number;
  delivery_success?: boolean;
  started_at?: string;
  completed_at?: string;
}

export interface ActiveSessionInfo {
  sessionId: string;
  task: string;
  status: 'running' | 'completed' | 'failed';
  phase: string;
  articleCount: number;
}

export interface SessionLaunchPayload {
  subject: string;
  topics: string[];
  researchInstructions?: string;
  title?: string;
}

export interface CollectedSource {
  id: string;
  session_id: string;
  session_brief: string;
  step_id?: string | null;
  step_name?: string | null;
  article_id?: string | null;
  title: string;
  url: string;
  source: string;
  topic?: string | null;
  summary?: string | null;
  published_date?: string | null;
  relevance_score?: number | null;
  tool_name?: string | null;
  created_at?: string | null;
}

export interface EmailGroupRecipient {
  email: string;
  label?: string | null;
}

export interface LinkedWatchProfileSummary {
  id: string;
  name: string;
}

export interface EmailGroupSummary {
  id: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  recipient_count: number;
}

export interface EmailGroup extends EmailGroupSummary {
  recipients: EmailGroupRecipient[];
  linked_watch_profiles: LinkedWatchProfileSummary[];
  created_at?: string;
  updated_at?: string;
}

export interface WatchProfile {
  id: string;
  name: string;
  subject?: string | null;
  topics: string[];
  depth: 'brief' | 'standard' | 'deep';
  format: 'digest' | 'report' | 'newsletter';
  angle?: string;
  sources?: string[];
  language?: string;
  audience?: string;
  focus?: string;
  is_active: boolean;
  last_run_at?: string;
  schedule_time?: string;
  schedule_days: string[];
  schedule_type?: 'weekly' | 'once' | 'monthly' | 'custom';
  schedule_date?: string;
  schedule_interval_months?: number;
  email_groups: EmailGroupSummary[];
  created_at?: string;
  updated_at?: string;
}

export interface WatchProfileRunResponse {
  success: boolean;
  session_id?: string | null;
  profile: string;
  task?: string;
  report?: string | null;
  email_sent?: boolean;
  result?: Record<string, any>;
  error?: string;
}

export interface SystemStats {
  total_articles: number;
  total_users: number;
  total_newsletter_runs: number;
  successful_deliveries: number;
  active_sessions: number;
}
