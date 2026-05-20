import { useState, useEffect, useRef } from 'react';
import type { PlanStep } from '../types';

export interface StreamArticle {
  title: string;
  url: string;
  source: string;
  published_date?: string;
  summary?: string;
  relevance_score?: number;
}

export const useOrchestratorStream = (url: string | null) => {
  const [report, setReport] = useState('');
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const [articles, setArticles] = useState<StreamArticle[]>([]);
  const [phase, setPhase] = useState('idle');
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!url) return;

    // Reset
    setReport('');
    setPlan([]);
    setArticles([]);
    setPhase('initializing');
    setStatus('running');
    setError(null);
    setSessionId(null);

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener('session_created', (e) => {
      const data = JSON.parse(e.data);
      setSessionId(data.session_id ?? null);
    });

    es.addEventListener('phase_transition', (e) => {
      const data = JSON.parse(e.data);
      setPhase(data.phase ?? '');
    });

    es.addEventListener('plan_updated', (e) => {
      const data = JSON.parse(e.data);
      if (Array.isArray(data.plan)) setPlan(data.plan);
    });

    es.addEventListener('research_result', (e) => {
      const data = JSON.parse(e.data);
      const incoming: StreamArticle[] = (data.articles ?? []).filter((a: StreamArticle) => a.url);
      if (incoming.length > 0) {
        setArticles(prev => {
          const existingUrls = new Set(prev.map(a => a.url));
          const newOnes = incoming.filter(a => !existingUrls.has(a.url));
          return [...prev, ...newOnes];
        });
      }
    });

    es.addEventListener('report_chunk', (e) => {
      const data = JSON.parse(e.data);
      if (data.chunk) setReport(prev => prev + data.chunk);
    });

    es.addEventListener('report_completed', () => {
      // report is fully assembled via chunks; mark phase done
      setPhase('completed');
    });

    es.addEventListener('session_completed', () => {
      setStatus('completed');
      setPhase('done');
      es.close();
    });

    es.addEventListener('session_failed', (e) => {
      const data = JSON.parse(e.data);
      setError(data.error ?? 'Erreur inconnue');
      setStatus('failed');
      es.close();
    });

    es.onerror = () => {
      // Only treat as error if we never completed
      setStatus(prev => prev === 'running' ? 'failed' : prev);
      setError(prev => prev ?? 'Connexion SSE perdue');
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [url]);

  return { report, plan, articles, phase, status, error, sessionId };
};
