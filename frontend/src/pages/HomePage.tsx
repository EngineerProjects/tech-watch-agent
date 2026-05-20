import React, { useState, useEffect } from 'react';
import {
  Zap,
  Search,
  Plus,
  ArrowUpRight,
  Database,
  Send,
  Clock,
  ChevronRight,
  FileText,
  CheckCircle2,
  AlertCircle,
  PlayCircle,
  Loader2
} from 'lucide-react';
import { ApiService } from '../services/api';
import type { ResearchSession } from '../types';
import { SessionStatus } from '../types';

const StatCard = ({ icon: Icon, title, value, trend, color, sparklinePoints }: any) => (
  <div className="card" style={{
    padding: 'var(--spacing-lg)',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    flex: 1,
    minWidth: '240px',
    position: 'relative',
    overflow: 'hidden'
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
      <Icon size={16} color={color} />
      <span>{title}</span>
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
      {trend && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: color }}>
          <ArrowUpRight size={14} />
          <span>{trend}</span>
        </div>
      )}
    </div>
    <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '40px' }}>
      <svg width="100%" height="40" viewBox="0 0 200 40" preserveAspectRatio="none">
        <path d={sparklinePoints} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" style={{ opacity: 0.6 }} />
        <path d={`${sparklinePoints} L 200 40 L 0 40 Z`} fill={`url(#gradient-${title.replace(/\s+/g, '')})`} style={{ opacity: 0.1 }} />
        <defs>
          <linearGradient id={`gradient-${title.replace(/\s+/g, '')}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color} />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  </div>
);

const statusLabel: Record<string, string> = {
  completed: 'COMPLÉTÉ',
  running: 'EN COURS',
  failed: 'ÉCHEC',
  created: 'PROGRAMMÉ',
  paused: 'PAUSÉ',
};

const RecentInvestigationRow = ({ session, onClick }: { session: ResearchSession; onClick: (id: string) => void }) => {
  const status = session.status;
  const isRunning = status === SessionStatus.RUNNING;
  const isFailed = status === SessionStatus.FAILED;

  const dateStr = new Date(session.created_at).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div
      onClick={() => onClick(session.id)}
      className="card"
      style={{
        padding: '12px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '20px',
        cursor: 'pointer',
        border: '1px solid var(--border-color)',
        backgroundColor: 'rgba(255,255,255,0.01)'
      }}
    >
      <div style={{
        width: '36px',
        height: '36px',
        borderRadius: '8px',
        backgroundColor: 'rgba(255,255,255,0.05)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: isRunning ? 'var(--status-running)' : isFailed ? 'var(--status-error)' : 'var(--status-success)'
      }}>
        <FileText size={20} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0 }}>
        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {session.research_brief}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', backgroundColor: 'rgba(255,255,255,0.03)', padding: '2px 8px', borderRadius: '4px', textTransform: 'capitalize' }}>
            {session.phase}
          </span>
        </div>
      </div>

      <div style={{ width: '100px', flexShrink: 0 }}>
        <div className="badge" style={{
          backgroundColor: isRunning ? 'var(--status-running-bg)' : isFailed ? 'var(--status-error-bg)' : 'var(--status-success-bg)',
          color: isRunning ? 'var(--status-running)' : isFailed ? 'var(--status-error)' : 'var(--status-success)',
          fontSize: '0.7rem'
        }}>
          {isRunning ? <PlayCircle size={12} className="animate-pulse" /> : isFailed ? <AlertCircle size={12} /> : <CheckCircle2 size={12} />}
          {statusLabel[status] ?? status.toUpperCase()}
        </div>
      </div>

      <div style={{ width: '140px', fontSize: '0.85rem', color: 'var(--text-secondary)', flexShrink: 0 }}>{dateStr}</div>

      <ChevronRight size={18} color="var(--text-muted)" />
    </div>
  );
};

export const HomePage: React.FC<{ onNewAnalysis: () => void; onSessionClick: (id: string) => void }> = ({ onNewAnalysis, onSessionClick }) => {
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ApiService.getSessions(5)
      .then(data => {
        setSessions(data.sessions);
        setTotal(data.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const completedCount = sessions.filter(s => s.status === SessionStatus.COMPLETED).length;
  const runningCount = sessions.filter(s => s.status === SessionStatus.RUNNING).length;

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>

      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: '2.2rem', fontWeight: 800, marginBottom: '8px' }}>Tableau de bord</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>Votre agent de veille technologique personnel</p>
        </div>
        <button
          onClick={onNewAnalysis}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 24px',
            backgroundColor: 'var(--accent-primary)',
            borderRadius: '10px',
            color: 'white',
            fontWeight: 600,
            fontSize: '0.95rem',
            boxShadow: '0 4px 20px rgba(124, 140, 255, 0.3)'
          }}
        >
          <Plus size={18} /> Nouvelle analyse
        </button>
      </header>

      {/* Search Section */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ position: 'relative', width: '100%' }}>
          <Search size={20} style={{ position: 'absolute', left: '20px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Quel sujet voulez-vous explorer aujourd'hui ?"
            style={{
              width: '100%',
              padding: '18px 20px 18px 56px',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
              color: 'var(--text-primary)',
              fontSize: '1.05rem',
              outline: 'none',
              boxShadow: '0 4px 30px rgba(0,0,0,0.1)'
            }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Sujets populaires</span>
          {['LLM Open Source', 'Agents IA', 'Diffusion Models', 'Startups IA', 'Papers Récents'].map(topic => (
            <button key={topic} style={{ padding: '6px 14px', borderRadius: '20px', backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              {topic}
            </button>
          ))}
        </div>
      </section>

      {/* Stats Grid */}
      <section style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
        <StatCard
          icon={Zap}
          title="Sessions lancées"
          value={loading ? '...' : String(total)}
          trend={runningCount > 0 ? `${runningCount} en cours` : undefined}
          color="var(--accent-purple)"
          sparklinePoints="M 0 30 Q 25 10 50 25 T 100 15 T 150 20 T 200 5"
        />
        <StatCard
          icon={Database}
          title="Complétées"
          value={loading ? '...' : String(completedCount)}
          color="var(--accent-secondary)"
          sparklinePoints="M 0 35 Q 20 20 40 30 T 80 15 T 120 25 T 160 10 T 200 20"
        />
        <StatCard
          icon={Send}
          title="En cours"
          value={loading ? '...' : String(runningCount)}
          color="var(--accent-primary)"
          sparklinePoints="M 0 25 Q 30 35 60 15 T 120 20 T 180 5 T 200 10"
        />
        <StatCard
          icon={Clock}
          title="Temps économisé"
          value={loading ? '...' : `${total * 30}min`}
          trend="Estimation"
          color="var(--accent-primary)"
          sparklinePoints="M 0 35 Q 50 30 100 15 T 150 25 T 200 5"
        />
      </section>

      {/* Recent Investigations */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Investigations récentes</h2>
          <button style={{ color: 'var(--accent-primary)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 500 }}>
            Voir toutes les sessions <ChevronRight size={16} />
          </button>
        </div>

        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '40px', justifyContent: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={20} className="animate-spin" />
            <span>Chargement des sessions...</span>
          </div>
        ) : sessions.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {sessions.map(s => (
              <RecentInvestigationRow key={s.id} session={s} onClick={onSessionClick} />
            ))}
          </div>
        ) : (
          <div className="card" style={{ padding: '48px', textAlign: 'center' }}>
            <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>Aucune session pour l'instant.</p>
            <button
              onClick={onNewAnalysis}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 20px', backgroundColor: 'var(--accent-primary)', borderRadius: '8px', color: 'white', fontWeight: 600 }}
            >
              <Plus size={16} /> Lancer une première analyse
            </button>
          </div>
        )}
      </section>
    </div>
  );
};
