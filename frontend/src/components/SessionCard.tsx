import React from 'react';
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
  RotateCw
} from 'lucide-react';
import type { ResearchSession } from '../types';
import { SessionStatus } from '../types';

interface SessionCardProps {
  session: ResearchSession;
  onClick: (id: string) => void;
}

const statusConfig: any = {
  [SessionStatus.COMPLETED]: {
    color: 'var(--status-success)',
    bgColor: 'rgba(34, 197, 94, 0.1)',
    label: 'TERMINÉE',
    icon: CheckCircle2
  },
  [SessionStatus.RUNNING]: {
    color: 'var(--status-running)',
    bgColor: 'rgba(59, 130, 246, 0.1)',
    label: 'EN COURS',
    icon: Play
  },
  [SessionStatus.FAILED]: {
    color: 'var(--status-error)',
    bgColor: 'rgba(239, 68, 68, 0.1)',
    label: 'ÉCHOUÉE',
    icon: ShieldAlert
  },
  [SessionStatus.CREATED]: {
    color: 'var(--status-warning)',
    bgColor: 'rgba(245, 158, 11, 0.1)',
    label: 'PROGRAMMÉE',
    icon: Clock
  }
};

// Map icons based on topic/content keywords (Mock logic for the vision)
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

export const SessionCard: React.FC<SessionCardProps> = ({ session, onClick }) => {
  const config = statusConfig[session.status] || statusConfig[SessionStatus.CREATED];
  const { icon: TopicIcon, color: topicColor } = getTopicIcon(session.research_brief);
  
  const isFailed = session.status === SessionStatus.FAILED;

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
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div style={{ 
            width: '48px', 
            height: '48px', 
            borderRadius: '12px', 
            backgroundColor: 'rgba(255,255,255,0.03)', 
            border: '1px solid var(--border-color)',
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            color: topicColor
          }}>
            <TopicIcon size={24} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: config.color, letterSpacing: '0.05em' }}>
                {config.label}
              </span>
            </div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              {session.research_brief}
            </h3>
          </div>
        </div>
        <button style={{ color: 'var(--text-muted)' }}><MoreVertical size={20} /></button>
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>
        {session.meta_data?.description || "Analyse automatique des tendances et nouveautés sur ce sujet."}
      </p>

      {/* Schedule Info */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          <Calendar size={14} />
          <span>{session.meta_data?.schedule_text || "Session unique"}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          <RotateCw size={14} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>Créée le</span>
            <span style={{ color: 'var(--text-secondary)' }}>
              {new Date(session.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        </div>
      </div>

      {/* Error State Banner */}
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
          color: 'var(--status-error)'
        }}>
          <AlertCircle size={14} />
          <span style={{ flex: 1 }}>Erreur lors de l'analyse des sources</span>
          <ChevronRight size={14} />
        </div>
      )}

      {/* Footer Metrics */}
      <div style={{ 
        marginTop: 'auto', 
        paddingTop: '20px', 
        borderTop: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', gap: '24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Dernière mise à jour</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              {relativeTime(session.completed_at || session.updated_at)}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Itérations</span>
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
            border: '1px solid var(--border-color)'
          }}
        >
          <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
};
