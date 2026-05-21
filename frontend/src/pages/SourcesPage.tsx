import React, { useEffect, useMemo, useState } from 'react';
import {
  Search,
  ExternalLink,
  Globe,
  MessageSquare,
  FileText,
  GitBranch,
  Play,
  Loader2,
} from 'lucide-react';
import { ApiService } from '../services/api';
import type { CollectedSource } from '../types';

type SourceCategory = 'all' | 'papers' | 'github' | 'reddit' | 'videos' | 'web';

function getSourceMeta(url: string, tool?: string, source?: string) {
  const u = (url || '').toLowerCase();
  const t = (tool || source || '').toLowerCase();
  if (u.includes('arxiv.org') || u.includes('doi.org') || t.includes('arxiv') || t.includes('semantic')) {
    return { icon: FileText, color: '#ef4444', label: 'Paper', category: 'papers' as SourceCategory };
  }
  if (u.includes('github.com') || t.includes('github')) {
    return { icon: GitBranch, color: '#94a3b8', label: 'GitHub', category: 'github' as SourceCategory };
  }
  if (u.includes('reddit.com') || t.includes('reddit')) {
    return { icon: MessageSquare, color: '#ff4500', label: 'Reddit', category: 'reddit' as SourceCategory };
  }
  if (u.includes('youtube.com') || u.includes('youtu.be') || t.includes('youtube')) {
    return { icon: Play, color: '#ff0000', label: 'Vidéo', category: 'videos' as SourceCategory };
  }
  return { icon: Globe, color: '#60a5fa', label: 'Web', category: 'web' as SourceCategory };
}

function formatRelevance(value?: number | null): string {
  if (typeof value !== 'number') return '—';
  const score = value <= 1 ? Math.round(value * 100) : Math.round(value);
  return `${score}%`;
}

const SourceRow = ({ source }: { source: CollectedSource }) => {
  const { icon: Icon, color, label } = getSourceMeta(source.url, source.tool_name || undefined, source.source);
  const dateLabel = source.published_date
    ? new Date(source.published_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
    : source.created_at
      ? new Date(source.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
      : '—';
  let domain = source.source || '—';
  try {
    domain = new URL(source.url).hostname.replace('www.', '');
  } catch { /* noop */ }

  return (
    <div className="card" style={{
      padding: '16px 24px',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '20px',
      backgroundColor: 'rgba(255,255,255,0.01)',
      border: '1px solid var(--border-color)',
    }}>
      <div style={{
        width: '38px', height: '38px', borderRadius: '10px', backgroundColor: 'rgba(255,255,255,0.03)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon size={18} color={color} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px', minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
          <div style={{ minWidth: 0 }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
              {source.title}
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)', fontSize: '0.78rem', flexWrap: 'wrap' }}>
              <span style={{ color, fontWeight: 600 }}>{label}</span>
              <span>{domain}</span>
              <span>•</span>
              <span>{dateLabel}</span>
              {source.step_name && (<><span>•</span><span>{source.step_name}</span></>)}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Pertinence</div>
              <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--status-success)' }}>{formatRelevance(source.relevance_score)}</div>
            </div>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ width: '36px', height: '36px', borderRadius: '8px', backgroundColor: 'rgba(255,255,255,0.03)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}
            >
              <ExternalLink size={16} />
            </a>
          </div>
        </div>

        <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
          Session: <span style={{ color: 'var(--text-primary)' }}>{source.session_brief}</span>
        </div>

        {source.summary && (
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: '1.55', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any }}>
            {source.summary}
          </p>
        )}
      </div>
    </div>
  );
};

export const SourcesPage: React.FC = () => {
  const [sources, setSources] = useState<CollectedSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [category, setCategory] = useState<SourceCategory>('all');

  useEffect(() => {
    setLoading(true);
    setError(null);
    ApiService.getSources({ limit: 200 })
      .then(setSources)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredSources = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return sources.filter(source => {
      const meta = getSourceMeta(source.url, source.tool_name || undefined, source.source);
      const matchesCategory = category === 'all' || meta.category === category;
      const matchesQuery = !q || [source.title, source.summary, source.session_brief, source.source, source.topic]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(q));
      return matchesCategory && matchesQuery;
    });
  }, [sources, searchQuery, category]);

  const counts = useMemo(() => ({
    all: sources.length,
    papers: sources.filter(source => getSourceMeta(source.url, source.tool_name || undefined, source.source).category === 'papers').length,
    github: sources.filter(source => getSourceMeta(source.url, source.tool_name || undefined, source.source).category === 'github').length,
    reddit: sources.filter(source => getSourceMeta(source.url, source.tool_name || undefined, source.source).category === 'reddit').length,
    videos: sources.filter(source => getSourceMeta(source.url, source.tool_name || undefined, source.source).category === 'videos').length,
    web: sources.filter(source => getSourceMeta(source.url, source.tool_name || undefined, source.source).category === 'web').length,
  }), [sources]);

  return (
    <div className="fade-in page-container" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Sources</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>Explorez l'ensemble des ressources collectées par vos sessions de veille</p>
        </div>

        <div style={{ position: 'relative' }}>
          <Search size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Rechercher dans les sources..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{ width: '320px', padding: '10px 16px 10px 44px', backgroundColor: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-color)', borderRadius: '10px', color: 'var(--text-primary)', fontSize: '0.9rem', outline: 'none' }}
          />
        </div>
      </header>

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        {([
          ['all', 'Toutes'],
          ['papers', 'Papers'],
          ['github', 'GitHub'],
          ['reddit', 'Reddit'],
          ['videos', 'Vidéos'],
          ['web', 'Web'],
        ] as [SourceCategory, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setCategory(key)}
            style={{
              padding: '6px 16px', borderRadius: '20px', fontSize: '0.85rem',
              backgroundColor: category === key ? 'rgba(124, 140, 255, 0.1)' : 'rgba(255,255,255,0.03)',
              color: category === key ? 'var(--accent-primary)' : 'var(--text-secondary)',
              border: '1px solid', borderColor: category === key ? 'rgba(124, 140, 255, 0.3)' : 'var(--border-color)',
              fontWeight: category === key ? 600 : 400,
            }}
          >
            {label} {counts[key]}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '100px' }}>
          <Loader2 size={28} className="animate-spin" color="var(--accent-primary)" />
        </div>
      ) : error ? (
        <div className="card" style={{ padding: '24px', backgroundColor: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444' }}>
          {error}
        </div>
      ) : filteredSources.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredSources.map(source => (
            <SourceRow key={source.id} source={source} />
          ))}
        </div>
      ) : (
        <div className="card" style={{ padding: '48px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Aucune source normalisée disponible pour le moment.
        </div>
      )}

      <style>{`
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};
