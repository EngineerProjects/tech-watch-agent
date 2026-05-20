import React, { useEffect, useState } from 'react';
import { 
  Search, 
  Filter, 
  ExternalLink, 
  Globe,
  MessageSquare,
  FileText,
  X,
  ChevronDown,
  Play
} from 'lucide-react';

const SourceRow = ({ title, domain, date, relevance, source, url }: any) => {
  const getIcon = (s: string) => {
    const src = s.toLowerCase();
    if (src.includes('arxiv')) return { icon: X, color: '#EF4444' };
    if (src.includes('github')) return { icon: Globe, color: '#111827' };
    if (src.includes('reddit')) return { icon: MessageSquare, color: '#FF4500' };
    if (src.includes('youtube')) return { icon: Play, color: '#FF0000' };
    return { icon: FileText, color: '#94A3B8' };
  };

  const { icon: Icon, color } = getIcon(source);

  return (
    <div className="card" style={{ 
      padding: '16px 24px', 
      display: 'flex', 
      alignItems: 'center', 
      gap: '24px',
      backgroundColor: 'rgba(255,255,255,0.01)',
      border: '1px solid var(--border-color)',
      transition: 'all 0.2s ease'
    }}>
      <div style={{ 
        width: '36px', 
        height: '36px', 
        borderRadius: '8px', 
        backgroundColor: 'rgba(255,255,255,0.03)', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        color: 'white',
        flexShrink: 0
      }}>
        <Icon size={20} color={color === '#111827' ? '#fff' : color} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>{title}</h4>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          <span style={{ color: 'var(--accent-secondary)' }}>{domain}</span>
          <span>•</span>
          <span>{source}</span>
          <span>•</span>
          <span>Collecté le {date}</span>
        </div>
      </div>

      <div style={{ width: '120px', textAlign: 'right' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Pertinence</div>
        <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--status-success)' }}>{relevance}%</div>
      </div>

      <a 
        href={url} 
        target="_blank" 
        rel="noopener noreferrer" 
        style={{ 
          width: '36px', 
          height: '36px', 
          borderRadius: '8px', 
          backgroundColor: 'rgba(255,255,255,0.03)', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          color: 'var(--text-secondary)',
          border: '1px solid var(--border-color)'
        }}
      >
        <ExternalLink size={16} />
      </a>
    </div>
  );
};

export const SourcesPage: React.FC = () => {
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    // Simulating fetching articles from global article store
    setTimeout(() => {
      setSources([
        { id: 1, title: "Llama 3: The Next Generation of Open Large Language Models", domain: "arxiv.org", date: "12 Mai 2024", relevance: 98, source: "arXiv", url: "#" },
        { id: 2, title: "meta-llama/llama3", domain: "github.com", date: "11 Mai 2024", relevance: 96, source: "GitHub", url: "#" },
        { id: 3, title: "Analyse comparative des performances de GPT-4o vs Claude 3.5", domain: "medium.com", date: "10 Mai 2024", relevance: 92, source: "Web", url: "#" },
        { id: 4, title: "r/LocalLLaMA: How to run Llama 3 70B on a single Mac Studio", domain: "reddit.com", date: "09 Mai 2024", relevance: 88, source: "Reddit", url: "#" },
        { id: 5, title: "Mistral NeMo: A new 12B model for edge devices", domain: "mistral.ai", date: "08 Mai 2024", relevance: 95, source: "Web", url: "#" },
        { id: 6, title: "Implementing RAG with LangGraph and VectorDB", domain: "youtube.com", date: "07 Mai 2024", relevance: 85, source: "YouTube", url: "#" },
      ]);
      setLoading(false);
    }, 500);
  }, []);

  return (
    <div className="fade-in" style={{ padding: '40px 60px', maxWidth: '1400px', margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Sources</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>Explorez l'ensemble des ressources collectées par vos agents</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              placeholder="Rechercher dans les sources..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '320px',
                padding: '10px 16px 10px 44px',
                backgroundColor: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>
          <button style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            color: 'var(--text-primary)',
            fontSize: '0.9rem'
          }}>
            <Filter size={18} /> Filtres
          </button>
        </div>
      </header>

      {/* Filter Chips */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        {['Toutes', 'arXiv', 'GitHub', 'Reddit', 'YouTube', 'Articles Web', 'Papers'].map((cat, i) => (
          <button 
            key={cat}
            style={{ 
              padding: '6px 16px', 
              borderRadius: '20px', 
              fontSize: '0.85rem', 
              backgroundColor: i === 0 ? 'rgba(124, 140, 255, 0.1)' : 'rgba(255,255,255,0.03)',
              color: i === 0 ? 'var(--accent-primary)' : 'var(--text-secondary)',
              border: '1px solid',
              borderColor: i === 0 ? 'rgba(124, 140, 255, 0.3)' : 'var(--border-color)',
              fontWeight: i === 0 ? 600 : 400
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '100px' }}>
          <div className="animate-spin" style={{ width: '32px', height: '32px', border: '3px solid var(--bg-surface)', borderTop: '3px solid var(--accent-primary)', borderRadius: '50%' }} />
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {sources.map(source => (
            <SourceRow key={source.id} {...source} />
          ))}
        </div>
      )}

      {!loading && sources.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '20px' }}>
          <button style={{ color: 'var(--text-muted)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            Charger plus de sources <ChevronDown size={16} />
          </button>
        </div>
      )}
    </div>
  );
};
