import React, { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { useOrchestratorStream, type StepResult, type StreamArticle, type SubscribeFn } from '../hooks/useOrchestratorStream';
import { StepStatus } from '../types';
import type { ResearchSession, PlanStep } from '../types';
import { ApiService } from '../services/api';
import {
  CheckCircle2, Circle, AlertCircle, Globe, GitBranch,
  Play, MessageCircle, FileText, ExternalLink, Download,
  ChevronRight, Loader2, Clock,
} from 'lucide-react';

interface SessionDetailPageProps {
  sessionId?: string;
  streamUrl?: string | null;
  subscribe?: SubscribeFn;
}

type Tab = 'report' | 'overview' | 'metadata';
type SourceFilter = 'all' | 'papers' | 'github' | 'reddit' | 'videos' | 'web';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getSourceMeta(url: string, tool?: string) {
  const u = (url || '').toLowerCase();
  const t = (tool || '').toLowerCase();
  if (u.includes('arxiv.org') || u.includes('doi.org') || t === 'arxiv' || t === 'semantic_scholar' || t === 'openalex' || t === 'research_paper') {
    return { Icon: FileText, color: '#ef4444', bg: 'rgba(239,68,68,0.15)', label: 'arXiv', filter: 'papers' as SourceFilter };
  }
  if (u.includes('github.com') || t === 'github') {
    return { Icon: GitBranch, color: '#8b949e', bg: 'rgba(139,148,158,0.15)', label: 'GitHub', filter: 'github' as SourceFilter };
  }
  if (u.includes('reddit.com') || t === 'reddit') {
    return { Icon: MessageCircle, color: '#ff4500', bg: 'rgba(255,69,0,0.15)', label: 'Reddit', filter: 'reddit' as SourceFilter };
  }
  if (u.includes('youtube.com') || u.includes('youtu.be') || t === 'youtube') {
    return { Icon: Play, color: '#ff0000', bg: 'rgba(255,0,0,0.15)', label: 'YouTube', filter: 'videos' as SourceFilter };
  }
  return { Icon: Globe, color: '#6366f1', bg: 'rgba(99,102,241,0.15)', label: 'Web', filter: 'web' as SourceFilter };
}

function isRawJson(s?: string | null) {
  const t = s?.trim();
  return !!(t && (t.startsWith('{') || t.startsWith('[')));
}

function formatDuration(startedAt?: string, completedAt?: string): string {
  if (!startedAt) return '';
  const secs = Math.round(((completedAt ? new Date(completedAt) : new Date()).getTime() - new Date(startedAt).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

/** Flatten session.research_results from DB, which can be either flat articles or step-result objects */
function flattenResearchResults(raw: any[]): StreamArticle[] {
  if (!Array.isArray(raw) || raw.length === 0) return [];
  const first = raw[0];
  if (typeof first?.url === 'string') return raw as StreamArticle[];
  if (Array.isArray(first?.data)) {
    return raw.flatMap((r: any) =>
      (r.data || []).filter((a: any) => a?.url).map((a: any) => ({
        ...a,
        tool: r.tool,
        step_id: r.step_id,
      }))
    );
  }
  return [];
}

function normalizePlanSteps(raw: unknown): PlanStep[] {
  if (Array.isArray(raw)) return raw.filter((step): step is PlanStep => !!step && typeof step === 'object');
  if (raw && typeof raw === 'object' && Array.isArray((raw as { steps?: unknown[] }).steps)) {
    return (raw as { steps: unknown[] }).steps.filter((step): step is PlanStep => !!step && typeof step === 'object');
  }
  return [];
}

function buildPersistedStepResults(raw: unknown): Record<string, StepResult> {
  if (!Array.isArray(raw) || raw.length === 0) return {};

  const grouped: Record<string, StepResult> = {};
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;

    const stepId = typeof (item as { step_id?: unknown }).step_id === 'string'
      ? (item as { step_id: string }).step_id
      : undefined;
    const tool = typeof (item as { tool?: unknown }).tool === 'string'
      ? (item as { tool: string }).tool
      : '';

    if (stepId && Array.isArray((item as { data?: unknown[] }).data)) {
      const articles = (item as { data: unknown[] }).data
        .filter((article): article is StreamArticle => !!article && typeof article === 'object' && typeof (article as StreamArticle).url === 'string')
        .map(article => ({ ...article, tool, step_id: stepId }));
      grouped[stepId] = {
        tool,
        count: typeof (item as { count?: unknown }).count === 'number' ? (item as { count: number }).count : articles.length,
        articles,
      };
      continue;
    }

    if (!stepId || typeof (item as { url?: unknown }).url !== 'string') continue;

    const article = { ...(item as StreamArticle), tool, step_id: stepId };
    const existing = grouped[stepId] ?? { tool, count: 0, articles: [] };
    if (!existing.articles.some(entry => entry.url === article.url)) {
      existing.articles = [...existing.articles, article];
    }
    existing.count = existing.articles.length;
    grouped[stepId] = existing;
  }

  return grouped;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

const StepIcon = ({ status }: { status: string }) => {
  if (status === StepStatus.DONE) return <CheckCircle2 size={22} color="#22c55e" />;
  if (status === StepStatus.RUNNING) return (
    <div style={{ width: 22, height: 22, borderRadius: '50%', border: '2px solid rgba(99,102,241,0.25)', borderTop: '2px solid #6366f1', animation: 'spin 0.8s linear infinite', flexShrink: 0 }} />
  );
  if (status === StepStatus.FAILED) return <AlertCircle size={22} color="#ef4444" />;
  return <Circle size={22} color="var(--text-muted)" strokeWidth={1.5} />;
};

const PlanStepRow = ({
  step, index, total, isSelected, onClick, articleCount,
}: {
  step: PlanStep; index: number; total: number;
  isSelected: boolean; onClick: () => void; articleCount?: number;
}) => {
  const duration = formatDuration(step.started_at, step.completed_at);
  const cleanResult = !isRawJson(step.result) ? step.result : null;
  const count = articleCount ?? null;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', gap: '12px', position: 'relative', cursor: 'pointer',
        padding: '10px 12px', borderRadius: '8px',
        backgroundColor: isSelected ? 'rgba(99,102,241,0.1)' : 'transparent',
        border: isSelected ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
        transition: 'all 0.15s ease', marginBottom: '2px',
      }}
      onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'rgba(255,255,255,0.03)'; }}
      onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'; }}
    >
      {/* Connector line */}
      {index !== total - 1 && (
        <div style={{
          position: 'absolute', left: '23px', top: '46px', bottom: '-10px', width: '2px',
          backgroundColor: step.status === StepStatus.DONE ? 'rgba(34,197,94,0.25)' : 'var(--border-color)', zIndex: 0,
        }} />
      )}

      {/* Status icon */}
      <div style={{ paddingTop: '2px', zIndex: 1, flexShrink: 0 }}>
        <StepIcon status={step.status} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
          {step.started_at
            ? <span style={{ fontSize: '0.67rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{new Date(step.started_at).toLocaleTimeString()}</span>
            : <span />}
          {duration && (
            <span style={{ fontSize: '0.67rem', color: step.status === StepStatus.DONE ? '#22c55e' : 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '2px' }}>
              <Clock size={9} /> {duration}
            </span>
          )}
        </div>

        <h4 style={{
          fontSize: '0.875rem', fontWeight: 600, marginBottom: '3px',
          color: step.status === StepStatus.PENDING ? 'var(--text-muted)' : isSelected ? '#a5b4fc' : 'var(--text-primary)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {step.name}
        </h4>

        <p style={{
          fontSize: '0.73rem', color: 'var(--text-muted)', lineHeight: '1.4',
          overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any,
        }}>
          {step.description}
        </p>

        {step.status === StepStatus.DONE && (count != null || cleanResult) && (
          <span style={{
            display: 'inline-block', marginTop: '6px', fontSize: '0.7rem', color: '#22c55e',
            fontWeight: 600, backgroundColor: 'rgba(34,197,94,0.1)', padding: '2px 8px', borderRadius: '4px',
          }}>
            {count != null ? `${count} résultats` : cleanResult}
          </span>
        )}

        {step.error && (
          <div style={{ fontSize: '0.7rem', color: '#ef4444', backgroundColor: 'rgba(239,68,68,0.08)', padding: '3px 8px', borderRadius: '4px', marginTop: '4px' }}>
            {step.error}
          </div>
        )}
      </div>
    </div>
  );
};

const SourceCard = ({ article }: { article: StreamArticle }) => {
  const { Icon, color, bg, label } = getSourceMeta(article.url, article.tool || article.source);
  let domain = '—';
  try { domain = new URL(article.url).hostname.replace('www.', ''); } catch { /* noop */ }
  const date = article.published_date
    ? new Date(article.published_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
    : '';
  const relevance = article.relevance_score != null ? `${Math.round(article.relevance_score * 100)}%` : null;

  return (
    <div style={{
      padding: '12px 14px', borderRadius: '8px',
      backgroundColor: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)',
      display: 'flex', gap: '12px', alignItems: 'flex-start',
      transition: 'border-color 0.15s',
    }}>
      <div style={{ width: 32, height: 32, borderRadius: '8px', backgroundColor: bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Icon size={15} color={color} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
          <h4 style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: '1.3', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any }}>
            {article.title || article.url}
          </h4>
          {article.url && (
            <a href={article.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-muted)', flexShrink: 0, marginTop: '2px' }}>
              <ExternalLink size={12} />
            </a>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.67rem', color: color, backgroundColor: bg, padding: '1px 6px', borderRadius: '4px', fontWeight: 600 }}>{label}</span>
          <span style={{ fontSize: '0.67rem', color: 'var(--text-muted)' }}>{domain}</span>
          {date && <span style={{ fontSize: '0.67rem', color: 'var(--text-muted)' }}>· {date}</span>}
        </div>
        {relevance && (
          <div style={{ marginTop: '4px', fontSize: '0.67rem', color: 'var(--text-muted)' }}>
            Pertinence: <span style={{ color: '#22c55e', fontWeight: 600 }}>{relevance}</span>
          </div>
        )}
        {article.summary && (
          <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px', lineHeight: '1.4', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any }}>
            {article.summary}
          </p>
        )}
      </div>
    </div>
  );
};

// ─── Main Component ────────────────────────────────────────────────────────────

const phaseLabels: Record<string, string> = {
  idle: 'En attente',
  initializing: 'Initialisation…',
  planner: 'Génération du plan…',
  supervisor: 'Supervision…',
  dispatcher: 'Recherche en cours…',
  dispatcher_parallel: 'Recherche parallèle…',
  synthesizer: 'Synthèse du rapport…',
  emailer: 'Envoi par email…',
  mailer: 'Envoi par email…',
  completed: 'Terminé',
  done: 'Terminé',
  failed: 'Échec',
};

export const SessionDetailPage: React.FC<SessionDetailPageProps> = ({ streamUrl, sessionId, subscribe }) => {
  const {
    report: streamedReport,
    plan: streamedPlan,
    articles: streamedArticles,
    stepResults,
    phase,
    status,
    error: streamError,
    sessionId: streamedSessionId,
  } = useOrchestratorStream(subscribe ? null : (streamUrl || null), subscribe);

  const [activeTab, setActiveTab] = useState<Tab>('report');
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingSession, setLoadingSession] = useState(false);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');

  // Load session from DB (history view, not when streaming)
  useEffect(() => {
    if (!sessionId || streamUrl || subscribe) return;
    setLoadingSession(true);
    setLoadError(null);
    ApiService.getSession(sessionId)
      .then(s => setSession(s))
      .catch(err => setLoadError(err.message))
      .finally(() => setLoadingSession(false));
  }, [sessionId, streamUrl, subscribe]);

  // Auto-reload from DB when stream completes
  useEffect(() => {
    const resolvedId = streamedSessionId || sessionId;
    if (status !== 'completed' || !resolvedId) return;
    const timer = setTimeout(() => {
      setLoadingSession(true);
      ApiService.getSession(resolvedId)
        .then(s => setSession(s))
        .catch(() => {})
        .finally(() => setLoadingSession(false));
    }, 1500);
    return () => clearTimeout(timer);
  }, [status, streamedSessionId, sessionId]);

  // Auto-select synthesis step when report is available
  useEffect(() => {
    if (streamedReport && !selectedStepId) {
      // find synthesis step
      const synthStep = streamedPlan.find(s => s.step_type === 'synthesis' || s.step_type === 'analysis' || s.name.toLowerCase().includes('synth'));
      if (synthStep) setSelectedStepId(synthStep.step_id);
    }
  }, [streamedReport, streamedPlan, selectedStepId]);

  const planSteps = useMemo<PlanStep[]>(() => {
    if (streamedPlan.length > 0) return streamedPlan;
    return normalizePlanSteps(session?.plan);
  }, [streamedPlan, session?.plan]);
  const finalReport = streamedReport || session?.final_report || '';

  const persistedStepResults = useMemo(
    () => buildPersistedStepResults(session?.research_results),
    [session?.research_results],
  );

  const effectiveStepResults = useMemo(
    () => ({ ...persistedStepResults, ...stepResults }),
    [persistedStepResults, stepResults],
  );

  // Flatten sources from both streaming and DB
  const allSources: StreamArticle[] = useMemo(() => {
    if (streamedArticles.length > 0) return streamedArticles;
    return flattenResearchResults(session?.research_results ?? []);
  }, [streamedArticles, session?.research_results]);

  const filteredSources = useMemo(() => {
    if (sourceFilter === 'all') return allSources;
    return allSources.filter(a => getSourceMeta(a.url, a.tool || a.source).filter === sourceFilter);
  }, [allSources, sourceFilter]);

  const title = session?.title || session?.subject || session?.research_brief || 'Session en cours…';
  const effectiveStatus = status !== 'idle' ? status : (session?.status ?? 'idle');
  const effectiveError = streamError ?? (session?.status === 'failed' ? 'La session a échoué.' : null);
  const isStreaming = (!!streamUrl || !!subscribe) && status === 'running';

  // Source filter counts
  const filterCounts = useMemo(() => ({
    all: allSources.length,
    papers: allSources.filter(a => getSourceMeta(a.url, a.tool || a.source).filter === 'papers').length,
    github: allSources.filter(a => getSourceMeta(a.url, a.tool || a.source).filter === 'github').length,
    reddit: allSources.filter(a => getSourceMeta(a.url, a.tool || a.source).filter === 'reddit').length,
    videos: allSources.filter(a => getSourceMeta(a.url, a.tool || a.source).filter === 'videos').length,
    web: allSources.filter(a => getSourceMeta(a.url, a.tool || a.source).filter === 'web').length,
  }), [allSources]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: 'var(--bg-primary)' }}>

      {/* ── Header ── */}
      <header style={{ height: 'var(--header-height)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', padding: '0 24px', justifyContent: 'space-between', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.875rem', minWidth: 0 }}>
          <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Sessions</span>
          <ChevronRight size={13} color="var(--text-muted)" style={{ flexShrink: 0 }} />
          <span style={{ color: 'var(--text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {isStreaming && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '0.78rem', color: 'var(--status-running)', backgroundColor: 'var(--status-running-bg)', padding: '4px 14px', borderRadius: '20px', border: '1px solid rgba(59,130,246,0.25)' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: 'var(--status-running)', animation: 'pulse 1.5s ease-in-out infinite' }} />
              {phaseLabels[phase] ?? phase}
            </div>
          )}
          {effectiveStatus === 'completed' && !isStreaming && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', padding: '4px 14px', borderRadius: '20px' }}>
              <CheckCircle2 size={13} /> Terminé
            </div>
          )}
          {effectiveError && (
            <div style={{ fontSize: '0.78rem', color: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', padding: '4px 14px', borderRadius: '20px' }}>
              {effectiveError}
            </div>
          )}
          {finalReport && (
            <button
              onClick={() => {
                const blob = new Blob([finalReport], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = 'rapport.md'; a.click();
                URL.revokeObjectURL(url);
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '7px', color: 'var(--text-secondary)', fontSize: '0.875rem', fontWeight: 500 }}
            >
              <Download size={15} /> Exporter
            </button>
          )}
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── Column 1: Execution Plan ── */}
        <aside style={{ width: '280px', borderRight: '1px solid var(--border-color)', padding: '20px 12px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', flexShrink: 0 }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, paddingLeft: '12px' }}>Plan d'exécution</h2>

          {planSteps.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {planSteps.map((step, idx) => (
                <PlanStepRow
                  key={step.step_id || idx}
                  step={step}
                  index={idx}
                  total={planSteps.length}
                  isSelected={selectedStepId === step.step_id}
                  onClick={() => setSelectedStepId(prev => prev === step.step_id ? null : step.step_id)}
                  articleCount={effectiveStepResults[step.step_id]?.articles.length ?? effectiveStepResults[step.step_id]?.count}
                />
              ))}
            </div>
          ) : isStreaming ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.82rem', paddingLeft: '12px' }}>
              <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> En attente du plan…
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', paddingLeft: '12px' }}>Aucun plan disponible.</p>
          )}
        </aside>

        {/* ── Column 2: Main Content ── */}
        <main style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          {/* Tabs */}
          <nav style={{ display: 'flex', gap: '28px', padding: '0 40px', paddingTop: '20px', paddingBottom: '0', position: 'sticky', top: 0, backgroundColor: 'var(--bg-primary)', zIndex: 10, borderBottom: '1px solid var(--border-color)', flexShrink: 0 }}>
            {([['report', 'Rapport'], ['overview', 'Aperçu'], ['metadata', 'Métadonnées']] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                style={{
                  paddingBottom: '14px', fontSize: '0.9rem', fontWeight: activeTab === key ? 600 : 400,
                  color: activeTab === key ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  borderBottom: activeTab === key ? '2px solid var(--accent-primary)' : '2px solid transparent',
                  marginBottom: '-1px',
                }}
              >
                {label}
              </button>
            ))}
          </nav>

          <div style={{ flex: 1, padding: '40px', overflowY: 'auto' }}>
            <article className="markdown-report" style={{ maxWidth: '820px', margin: '0 auto', paddingBottom: '80px' }}>

              {/* ── REPORT TAB ── */}
              {activeTab === 'report' && (
                <>
                  {loadingSession ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '80px 0', gap: '16px' }}>
                      <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent-primary)' }} />
                      <p style={{ color: 'var(--text-secondary)' }}>Chargement de la session...</p>
                    </div>
                  ) : loadError ? (
                    <div className="card" style={{ padding: '24px', backgroundColor: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.2)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#ef4444' }}>
                        <AlertCircle size={22} />
                        <div>
                          <h3 style={{ color: '#ef4444', marginBottom: '4px' }}>Erreur de chargement</h3>
                          <p style={{ fontSize: '0.875rem', opacity: 0.8 }}>{loadError}</p>
                        </div>
                      </div>
                    </div>
                  ) : finalReport ? (
                    /* Report always shown — sources are already in the right panel */
                    <>
                      <ReactMarkdown>{finalReport}</ReactMarkdown>
                      {isStreaming && (
                        <span style={{ display: 'inline-block', width: '2px', height: '1.2em', backgroundColor: 'var(--accent-primary)', verticalAlign: 'text-bottom', marginLeft: '2px', animation: 'blink 1s step-end infinite' }} />
                      )}
                    </>
                  ) : isStreaming ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '80px 0', gap: '16px' }}>
                      <Loader2 size={28} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent-primary)' }} />
                      <p style={{ color: 'var(--text-secondary)' }}>{phaseLabels[phase] ?? 'Traitement en cours…'}</p>
                      <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>Le rapport apparaîtra ici à la fin de la synthèse.</p>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '80px 0' }}>
                      <p style={{ color: 'var(--text-muted)' }}>Aucun rapport disponible pour cette session.</p>
                    </div>
                  )}
                </>
              )}

              {/* ── OVERVIEW TAB ── */}
              {activeTab === 'overview' && session && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div className="card" style={{ padding: '24px' }}>
                    <h3 style={{ marginBottom: '16px', fontSize: '1.05rem', fontWeight: 600 }}>Informations générales</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '0.875rem' }}>
                      {([
                        ['Statut', session.status],
                        ['Phase', session.phase],
                        ['Créée le', new Date(session.created_at).toLocaleString('fr-FR')],
                        ['Mise à jour', new Date(session.updated_at).toLocaleString('fr-FR')],
                        ...(session.completed_at ? [['Terminée le', new Date(session.completed_at).toLocaleString('fr-FR')] as [string, string]] : []),
                        ['Sources collectées', String(allSources.length > 0 ? allSources.length : (session.research_results?.length ?? '—'))],
                      ] as [string, string][]).map(([label, value]) => (
                        <div key={label}>
                          <span style={{ color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontSize: '0.78rem' }}>{label}</span>
                          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  {session.analysis_results && (
                    <div className="card" style={{ padding: '24px' }}>
                      <h3 style={{ marginBottom: '12px', fontSize: '1.05rem', fontWeight: 600 }}>Analyse</h3>
                      <p style={{ color: 'var(--text-secondary)', lineHeight: '1.7', fontSize: '0.875rem', whiteSpace: 'pre-wrap' }}>{session.analysis_results}</p>
                    </div>
                  )}
                </div>
              )}

              {/* ── METADATA TAB ── */}
              {activeTab === 'metadata' && session && (
                <div className="card" style={{ padding: '24px' }}>
                  <h3 style={{ marginBottom: '12px', fontSize: '1.05rem', fontWeight: 600 }}>Métadonnées</h3>
                  <pre style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(session.meta_data ?? {}, null, 2)}
                  </pre>
                </div>
              )}
            </article>
          </div>
        </main>

        {/* ── Column 3: Sources ── */}
        <aside style={{ width: '360px', borderLeft: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', flexShrink: 0, backgroundColor: 'rgba(17,24,39,0.3)' }}>
          {/* Header */}
          <div style={{ padding: '20px 20px 0', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>
                Sources{allSources.length > 0 ? ` (${allSources.length})` : ''}
              </h2>
              {isStreaming && allSources.length > 0 && (
                <span style={{ fontSize: '0.7rem', color: 'var(--status-running)', backgroundColor: 'var(--status-running-bg)', padding: '2px 8px', borderRadius: '10px' }}>live</span>
              )}
            </div>

            {/* Filter chips */}
            {allSources.length > 0 && (
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
                {([
                  ['all', 'Toutes'],
                  ['papers', 'Papiers'],
                  ['github', 'GitHub'],
                  ['reddit', 'Reddit'],
                  ['videos', 'Vidéos'],
                  ['web', 'Web'],
                ] as [SourceFilter, string][]).map(([key, label]) => {
                  const cnt = filterCounts[key];
                  if (key !== 'all' && cnt === 0) return null;
                  return (
                    <button
                      key={key}
                      onClick={() => setSourceFilter(key)}
                      style={{
                        padding: '3px 10px', borderRadius: '20px', fontSize: '0.72rem', fontWeight: 500,
                        backgroundColor: sourceFilter === key ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)',
                        color: sourceFilter === key ? '#fff' : 'var(--text-secondary)',
                        border: sourceFilter === key ? 'none' : '1px solid var(--border-color)',
                        transition: 'all 0.15s',
                      }}
                    >
                      {label}{key !== 'all' ? ` ${cnt}` : ''}
                    </button>
                  );
                })}
              </div>
            )}
            <div style={{ borderBottom: '1px solid var(--border-color)' }} />
          </div>

          {/* Source list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 24px' }}>
            {filteredSources.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {filteredSources.map((a, i) => (
                  <SourceCard key={a.url || i} article={a} />
                ))}
              </div>
            ) : allSources.length > 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', textAlign: 'center', paddingTop: '24px' }}>
                Aucune source dans cette catégorie.
              </p>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', textAlign: 'center', paddingTop: '24px' }}>
                {isStreaming ? 'Collecte en cours…' : 'Aucune source collectée.'}
              </p>
            )}
          </div>
        </aside>
      </div>

      <style>{`
        .markdown-report { color: var(--text-secondary); }
        .markdown-report h1 { font-size: 2.2rem; font-weight: 700; margin-bottom: 1.5rem; color: var(--text-primary); line-height: 1.2; }
        .markdown-report h2 { font-size: 1.5rem; font-weight: 600; margin: 2.5rem 0 1rem; color: var(--text-primary); padding-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); }
        .markdown-report h3 { font-size: 1.15rem; font-weight: 600; margin: 2rem 0 0.75rem; color: var(--text-primary); }
        .markdown-report h4 { font-size: 1rem; font-weight: 600; margin: 1.5rem 0 0.5rem; color: var(--text-primary); }
        .markdown-report p { margin-bottom: 1.25rem; line-height: 1.75; }
        .markdown-report ul, .markdown-report ol { padding-left: 1.5rem; margin-bottom: 1.25rem; }
        .markdown-report li { margin-bottom: 0.4rem; line-height: 1.7; }
        .markdown-report strong { color: var(--text-primary); font-weight: 600; }
        .markdown-report em { font-style: italic; }
        .markdown-report a { color: var(--accent-primary); text-decoration: underline; text-decoration-style: dotted; }
        .markdown-report a:hover { text-decoration-style: solid; }
        .markdown-report code { background: rgba(255,255,255,0.06); padding: 2px 7px; border-radius: 4px; font-size: 0.83em; font-family: 'JetBrains Mono', 'Fira Code', monospace; color: #e2e8f0; }
        .markdown-report pre { background: rgba(0,0,0,0.3); padding: 20px; border-radius: 10px; overflow-x: auto; margin-bottom: 1.5rem; border: 1px solid var(--border-color); }
        .markdown-report pre code { background: none; padding: 0; }
        .markdown-report blockquote { border-left: 3px solid var(--accent-primary); padding-left: 16px; margin: 0 0 1.25rem; color: var(--text-muted); font-style: italic; }
        .markdown-report table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; font-size: 0.875rem; }
        .markdown-report th { background: rgba(255,255,255,0.05); padding: 10px 14px; text-align: left; font-weight: 600; color: var(--text-primary); border: 1px solid var(--border-color); }
        .markdown-report td { padding: 9px 14px; border: 1px solid var(--border-color); }
        .markdown-report hr { border: none; border-top: 1px solid var(--border-color); margin: 2rem 0; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
      `}</style>
    </div>
  );
};
