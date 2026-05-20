import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Send, Sparkles, Hash } from 'lucide-react';

interface LiveRunModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRun: (task: string, topics: string[]) => void;
}

export const LiveRunModal: React.FC<LiveRunModalProps> = ({ isOpen, onClose, onRun }) => {
  const [task, setTask] = useState('');
  const [topics, setTopics] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;
    
    const topicsList = topics.split(',').map(t => t.trim()).filter(t => t.length > 0);
    onRun(task, topicsList);
    setTask('');
    setTopics('');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          width: '100vw', height: '100vh',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 'var(--spacing-md)',
          boxSizing: 'border-box'
        }}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(4px)'
            }}
          />
          
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '600px',
              backgroundColor: 'var(--bg-surface)',
              borderRadius: '16px',
              border: '1px solid var(--border-color)',
              padding: 'var(--spacing-xl)',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.4)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--spacing-xl)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
                <Sparkles size={24} color="var(--accent-primary)" />
                <h2 style={{ fontSize: '1.5rem', margin: 0 }}>Lancer une Veille Live</h2>
              </div>
              <button onClick={onClose} style={{ color: 'var(--text-secondary)' }}>
                <X size={24} />
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xs)' }}>
                <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Sujet de la recherche
                </label>
                <textarea
                  autoFocus
                  required
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="Ex: Dernières avancées sur les modèles de raisonnement (O1, DeepSeek) en mai 2026..."
                  style={{
                    width: '100%',
                    minHeight: '100px',
                    padding: 'var(--spacing-md)',
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)',
                    fontSize: '1rem',
                    resize: 'none',
                    outline: 'none',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xs)' }}>
                <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Topics (séparés par des virgules)
                </label>
                <div style={{ position: 'relative' }}>
                  <Hash size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    value={topics}
                    onChange={(e) => setTopics(e.target.value)}
                    placeholder="ia, llm, raisonnement, benchmarks..."
                    style={{
                      width: '100%',
                      padding: '12px 12px 12px 40px',
                      backgroundColor: 'var(--bg-primary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)',
                      fontSize: '0.9rem',
                      outline: 'none'
                    }}
                  />
                </div>
              </div>

              <div style={{ 
                marginTop: 'var(--spacing-md)',
                padding: 'var(--spacing-md)',
                backgroundColor: 'var(--status-running-bg)',
                borderRadius: '8px',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                display: 'flex',
                gap: 'var(--spacing-sm)',
                fontSize: '0.85rem',
                color: 'var(--status-running)'
              }}>
                <Sparkles size={16} style={{ flexShrink: 0 }} />
                <p>L'agent va générer un plan, collecter des sources en direct et synthétiser un rapport complet sous vos yeux.</p>
              </div>

              <button
                type="submit"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 'var(--spacing-sm)',
                  padding: '14px',
                  backgroundColor: 'var(--accent-primary)',
                  borderRadius: '8px',
                  color: 'white',
                  fontWeight: 600,
                  fontSize: '1rem',
                  marginTop: 'var(--spacing-sm)'
                }}
              >
                <Send size={18} />
                Lancer l'Agent
              </button>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
