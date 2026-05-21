import React, { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  Play,
  AlertCircle,
  Clock,
  MoreVertical,
  ChevronRight,
  Calendar,
  Bot,
  Sparkles,
  Rocket,
  FileText,
  ShieldAlert,
  Cpu,
  BarChart3,
  Globe,
  RotateCw,
  Trash2,
  Eye,
  RefreshCw,
} from 'lucide-react';
import type { ResearchSession } from '../types';
import { SessionStatus } from '../types';

interface SessionCardProps {
  session: ResearchSession;
  onClick: (id: string) => void;
  onDelete: (session: ResearchSession) => Promise<void> | void;
  onRerun: (session: ResearchSession) => void;
}

const statusConfig: any = {
  [SessionStatus.COMPLETED]: {
    color: 'var(--status-success)',
    bgColor: 'rgba(34, 197, 94, 0.1)',
    label: 'TERMINEE',
    icon: CheckCircle2,
  },
  [SessionStatus.RUNNING]: {
    color: 'var(--status-running)',
    bgColor: 'rgba(59, 130, 246, 0.1)',
    label: 'EN COURS',
    icon: Play,
  },
  [SessionStatus.FAILED]: {
    color: 'var(--status-error)',
    bgColor: 'rgba(239, 68, 68, 0.1)',
    label: 'ECHOUEE',
    icon: ShieldAlert,
  },
  [SessionStatus.CREATED]: {
    color: 'var(--status-warning)',
    bgColor: 'rgba(245, 158, 11, 0.1)',
    label: 'PROGRAMMEE',
    icon: Clock,
  },
};

const getTopicIcon = (title: string) => {
  const t = title.toLowerCase();
  if (t.includes('llm') || t.includes('ai')) return { icon: Bot, color: '#22C55E' };
  if (t.includes('startup') || t.includes('rocket')) return { icon: Rocket, color: '#F59E0B' };
  if (t.includes('diffusion') || t.includes('image')) return { icon: Sparkles, color: '#A78BFA' };
  if (t.includes('crypto')) return { icon: ShieldAlert, color: '#EF4444' };
  if (t.includes('hardware') || t.includes('cpu')) return { icon: Cpu, color: '#3B82F6' };
  if (t.includes('benchmarks')) return { icon: BarChart3, color: '#F97316' };
  if (t.includes('news') || t.includes('digest')) return { icon: Globe, color: '#7C8CFF' };
  return { icon: FileText, color: '#94A3B8' };
};

function relativeTime(dateStr?: string | null): string {
  if (!dateStr) return '—';
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffDays === 0) return "Aujourd'hui";
  if (diffDays === 1) return 'Hier';
  if (diffDays < 30) return `Il y a ${diffDays} j`;
  const diffMonths = Math.floor(diffDays / 30);
  return `Il y a ${diffMonths} mois`;
}

function getSessionTitle(session: ResearchSession): string {
  return session.title || session.subject || session.research_brief;
}

export const SessionCard: React.FC<SessionCardProps> = ({ session, onClick, onDelete, onRerun }) => {
  const config = statusConfig[session.status] || statusConfig[SessionStatus.CREATED];
  const title = getSessionTitle(session);
  const { icon: TopicIcon, color: topicColor } = getTopicIcon(title);
  const isFailed = session.status === SessionStatus.FAILED;
  const canRerun = session.status === SessionStatus.COMPLETED;
  const [menuOpen, setMenuOpen] = useState(false);
  const [busyAction, setBusyAction] = useState<'delete' | 'rerun' | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDocClick = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [menuOpen]);

  const runDelete = async () => {
    setBusyAction('delete');
    try {
      await onDelete(session);
    } finally {
      setBusyAction(null);
      setMenuOpen(false);
    }
  };

  const runRerun = async () => {
    setBusyAction('rerun');
    try {
      onRerun(session);
    } finally {
      setBusyAction(null);
      setMenuOpen(false);
    }
  };

  return (
    <div className="card" style={{
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
      position: 'relative',
      backgroundColor: 'rgba(17, 24, 39, 0.4)',
      border: '1px solid var(--border-color)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
        <div style={{ display: 'flex', gap: '16px', minWidth: 0 }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            backgroundColor: 'rgba(255,255,255,0.03)',
            border: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: topicColor,
            flexShrink: 0,
          }}>
            <TopicIcon size={24} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: config.color, letterSpacing: '0.05em' }}>
                {config.label}
              </span>
            </div>
            <h3 style={{
              fontSize: '1.05rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              margin: 0,
              overflow: 'hidden',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              lineHeight: '1.35',
            }}>
              {title}
            </h3>
          </div>
        </div>

        <div ref={menuRef} style={{ position: 'relative', flexShrink: 0 }}>
          <button
            onClick={() => setMenuOpen(open => !open)}
            style={{
              color: 'var(--text-muted)',
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              backgroundColor: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--border-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MoreVertical size={18} />
          </button>
          {menuOpen && (
            <div style={{
              position: 'absolute',
              top: '42px',
              right: 0,
              minWidth: '180px',
              backgroundColor: 'rgba(15, 23, 42, 0.98)',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.35)',
              padding: '8px',
              zIndex: 20,
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}>
              <button onClick={() => { setMenuOpen(false); onClick(session.id); }} style={menuItemStyle}>
                <Eye size={15} /> Ouvrir
              </button>
              {canRerun && (
                <button onClick={runRerun} disabled={busyAction !== null} style={menuItemStyle}>
                  <RefreshCw size={15} /> Relancer
                </button>
              )}
              <button onClick={runDelete} disabled={busyAction !== null} style={{ ...menuItemStyle, color: '#fca5a5' }}>
                <Trash2 size={15} /> Supprimer
              </button>
            </div>
          )}
        </div>
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>
        {session.subject && session.subject !== title ? session.subject : session.meta_data?.description || 'Analyse automatique des tendances et nouveautés sur ce sujet.'}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          <Calendar size={14} />
          <span>{session.meta_data?.schedule_text || 'Session unique'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          <RotateCw size={14} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>Creee le</span>
            <span style={{ color: 'var(--text-secondary)' }}>
              {new Date(session.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        </div>
      </div>

      {isFailed && (
        <div style={{
          padding: '10px 16px',
          backgroundColor: 'rgba(239, 68, 68, 0.05)',
          borderRadius: '8px',
          border: '1px solid rgba(239, 68, 68, 0.2)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          fontSize: '0.8rem',
          color: 'var(--status-error)',
        }}>
          <AlertCircle size={14} />
          <span style={{ flex: 1 }}>Erreur lors de l'analyse des sources</span>
          <ChevronRight size={14} />
        </div>
      )}

      <div style={{
        marginTop: 'auto',
        paddingTop: '20px',
        borderTop: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
      }}>
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Derniere mise a jour</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {relativeTime(session.completed_at || session.updated_at)}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Iterations</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 600 }}>
              {session.iterations_count ?? '—'}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Phase</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 600, textTransform: 'capitalize' }}>
              {session.phase}
            </span>
          </div>
        </div>

        <button
          onClick={() => onClick(session.id)}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            backgroundColor: 'rgba(255,255,255,0.05)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border-color)',
            flexShrink: 0,
          }}
        >
          <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
};

const menuItemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  width: '100%',
  padding: '10px 12px',
  borderRadius: '8px',
  color: 'var(--text-primary)',
  backgroundColor: 'transparent',
  fontSize: '0.88rem',
  textAlign: 'left',
};
