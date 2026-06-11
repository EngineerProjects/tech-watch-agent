import { useState, useEffect, useRef } from 'react';
import type { PlanStep } from '../types';

export interface StreamArticle {
  title: string;
  url: string;
  source: string;
  tool?: string;
  step_id?: string;
  published_date?: string;
  summary?: string;
  relevance_score?: number;
}

export interface StepResult {
  tool: string;
  count: number;
  articles: StreamArticle[];
}

export interface BusEvent { type: string; data: any }

export interface ApprovalInfo {
  sessionId: string;
  researchCount: number;
  qualityScore: number;
  message: string;
}

/**
 * Subscribe function type: caller provides a callback and receives an unsubscribe fn.
 * Used to connect to a shared EventSource managed by App.tsx instead of opening a new one.
 */
export type SubscribeFn = (cb: (evt: BusEvent) => void) => () => void;

export const useOrchestratorStream = (
  url: string | null,
  subscribe?: SubscribeFn,
) => {
  const [report, setReport] = useState('');
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const [articles, setArticles] = useState<StreamArticle[]>([]);
  const [stepResults, setStepResults] = useState<Record<string, StepResult>>({});
  const [phase, setPhase] = useState('idle');
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed' | 'awaiting_approval'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [approvalInfo, setApprovalInfo] = useState<ApprovalInfo | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setReport('');
    setPlan([]);
    setArticles([]);
    setStepResults({});
    setError(null);
    setSessionId(null);
    setApprovalInfo(null);

    if (url || subscribe) {
      setPhase('initializing');
      setStatus('running');
    } else {
      setPhase('idle');
      setStatus('idle');
    }

    const handleEvent = (type: string, data: any) => {
      if (type === 'session_created') {
        setSessionId(data.session_id ?? null);
      } else if (type === 'phase_transition') {
        setPhase(data.phase ?? '');
      } else if (type === 'plan_updated') {
        if (Array.isArray(data.plan)) setPlan(data.plan);
      } else if (type === 'research_result') {
        const stepId: string | undefined = data.step_id;
        const tool: string = data.tool ?? '';
        const count: number = data.count ?? 0;
        const incoming: StreamArticle[] = (data.articles ?? [])
          .filter((a: any) => a.url)
          .map((a: any) => ({ ...a, tool, step_id: stepId }));
        if (incoming.length > 0) {
          setArticles(prev => {
            const seen = new Set(prev.map(a => a.url));
            return [...prev, ...incoming.filter((a: StreamArticle) => !seen.has(a.url))];
          });
        }
        if (stepId) {
          setStepResults(prev => ({ ...prev, [stepId]: { tool, count, articles: incoming } }));
        }
      } else if (type === 'report_chunk') {
        if (data.chunk) setReport(prev => prev + data.chunk);
      } else if (type === 'report_completed') {
        setPhase('completed');
      } else if (type === 'session_completed') {
        setStatus('completed');
        setPhase('done');
      } else if (type === 'session_failed') {
        setError(data.error ?? 'Erreur inconnue');
        setStatus('failed');
        setPhase('failed');
      } else if (type === 'approval_required') {
        setStatus('awaiting_approval');
        setPhase('awaiting_approval');
        setApprovalInfo({
          sessionId: data.session_id ?? '',
          researchCount: data.research_count ?? 0,
          qualityScore: data.quality_score ?? 0,
          message: data.message ?? 'En attente de validation',
        });
      }
    };

    if (subscribe) {
      const unsubscribe = subscribe((evt) => {
        try { handleEvent(evt.type, evt.data); } catch { /* noop */ }
      });
      return unsubscribe;
    }

    if (!url) return;

    const es = new EventSource(url);
    esRef.current = es;

    const EVENT_TYPES = [
      'session_created', 'phase_transition', 'plan_updated',
      'research_result', 'report_chunk', 'report_completed',
      'session_completed', 'session_failed', 'approval_required',
    ] as const;

    for (const type of EVENT_TYPES) {
      es.addEventListener(type, (e) => {
        try { handleEvent(type, JSON.parse((e as MessageEvent).data)); } catch { /* noop */ }
      });
    }

    es.onerror = () => {
      setStatus(prev => prev === 'running' ? 'failed' : prev);
      setError(prev => prev ?? 'Connexion SSE perdue');
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [url, subscribe]);

  return { report, plan, articles, stepResults, phase, status, error, sessionId, approvalInfo };
};
