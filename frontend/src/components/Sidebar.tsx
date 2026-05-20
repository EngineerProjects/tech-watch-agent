import React from 'react';
import { LayoutDashboard, Compass, Mail, Settings, Zap, History, Search, Command } from 'lucide-react';

interface SidebarProps {
  currentPage: string;
  onPageChange: (page: any) => void;
}

const navItems = [
  { id: 'home',      label: 'Accueil',     icon: LayoutDashboard },
  { id: 'sessions',  label: 'Sessions',    icon: History },
  { id: 'newsletter',label: 'Newsletter',  icon: Mail },
  { id: 'sources',   label: 'Sources',     icon: Search },
  { id: 'topics',    label: 'Topics',      icon: Compass },
  { id: 'settings',  label: 'Paramètres',  icon: Settings },
];

export const Sidebar: React.FC<SidebarProps> = ({ currentPage, onPageChange }) => {
  return (
    <aside
      className="main-sidebar"
      style={{
        width: 'var(--sidebar-width)',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        backgroundColor: 'var(--bg-primary)',
        borderRight: '1px solid var(--border-color)',
        display: 'flex',
        flexDirection: 'column',
        padding: 'var(--spacing-xl) 0',
        zIndex: 100,
        overflow: 'hidden',
        transition: 'width 0.2s ease',
      }}
    >
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '40px', padding: '0 var(--sidebar-px, 24px)', minWidth: 0 }}>
        <div style={{
          width: '28px', height: '28px', flexShrink: 0,
          background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-purple))',
          borderRadius: '6px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 15px rgba(124,140,255,0.2)'
        }}>
          <Zap size={16} color="white" fill="white" />
        </div>
        <span className="sidebar-logo-text" style={{ fontWeight: 700, fontSize: '1.05rem', letterSpacing: '-0.02em', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden' }}>
          Tech Watch
        </span>
      </div>

      {/* Nav */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '0 8px', flex: 1 }}>
        {navItems.map(item => {
          const Icon = item.icon;
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onPageChange(item.id)}
              title={item.label}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 12px',
                borderRadius: '8px',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                backgroundColor: isActive ? 'rgba(124,140,255,0.1)' : 'transparent',
                fontWeight: isActive ? 600 : 400,
                fontSize: '0.9rem',
                textAlign: 'left',
                width: '100%',
                transition: 'all 0.2s ease',
                border: 'none',
                minWidth: 0,
                whiteSpace: 'nowrap',
              }}
            >
              <Icon size={18} color={isActive ? 'var(--accent-primary)' : 'var(--text-muted)'} style={{ flexShrink: 0 }} />
              <span className="sidebar-label" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="sidebar-bottom-section" style={{ padding: '0 12px' }}>
        <div style={{ padding: '0 12px', marginBottom: '20px' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '10px' }}>
            Raccourcis
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <Command size={10} /><span>K</span>
            </div>
            <span>Palette</span>
          </div>
        </div>

        <div style={{
          padding: '12px',
          borderRadius: '10px',
          backgroundColor: 'rgba(255,255,255,0.02)',
          border: '1px solid var(--border-color)',
          display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer'
        }}>
          <img
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=Alexandre"
            alt="Alexandre"
            style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: 'var(--bg-surface)', flexShrink: 0 }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Alexandre</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Admin</div>
          </div>
        </div>
      </div>
    </aside>
  );
};
