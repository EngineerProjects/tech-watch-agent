import { useState, useEffect } from 'react';
import type { PlanStep, Article } from '../types';

export interface StreamEvent {
  event: string;
  data: any;
}

export const useOrchestratorStream = (url: string | null) => {
  const [report, setReport] = useState('');
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [phase, setPhase] = useState('idle');
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!url) return;

    setReport('');
    setPlan([]);
    setArticles([]);
    setPhase('initializing');
    setStatus('running');
    setError(null);

    const eventSource = new EventSource(url);

    eventSource.addEventListener('session_created', (e) => {
      console.log('Session created:', JSON.parse(e.data));
    });

    eventSource.addEventListener('phase_transition', (e) => {
      const data = JSON.parse(e.data);
      setPhase(data.phase);
    });

    eventSource.addEventListener('plan_updated', (e) => {
      const data = JSON.parse(e.data);
      setPlan(data.plan);
    });

    eventSource.addEventListener('report_chunk', (e) => {
      const data = JSON.parse(e.data);
      setReport((prev) => prev + data.chunk);
    });

    eventSource.addEventListener('research_result', () => {
      // Backend currently sends minimal research_result info in SSE
    });

    eventSource.addEventListener('session_completed', () => {
      setStatus('completed');
      eventSource.close();
    });

    eventSource.addEventListener('session_failed', (e) => {
      const data = JSON.parse(e.data);
      setError(data.error);
      setStatus('failed');
      eventSource.close();
    });

    eventSource.onerror = (e) => {
      console.error('SSE Error:', e);
      setError('Connection lost');
      setStatus('failed');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [url]);

  return { report, plan, articles, phase, status, error };
};
