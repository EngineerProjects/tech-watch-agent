import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { HomePage } from './pages/HomePage';
import { SessionsPage } from './pages/SessionsPage';
import { SessionDetailPage } from './pages/SessionDetailPage';
import { TopicsPage } from './pages/TopicsPage';
import { NewsletterPage } from './pages/NewsletterPage';
import { SettingsPage } from './pages/SettingsPage';
import { LiveRunModal } from './components/LiveRunModal';
import { ApiService } from './services/api';

type Page = 'home' | 'sessions' | 'topics' | 'newsletter' | 'sources' | 'settings' | 'detail';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('home');
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleRunLive = (task: string, topics: string[]) => {
    const url = ApiService.getStreamUrl(task, topics);
    setStreamUrl(url);
    setSelectedSessionId(null);
    setIsModalOpen(false);
    setCurrentPage('detail');
  };

  const handleSessionClick = (id: string) => {
    setStreamUrl(null);
    setSelectedSessionId(id);
    setCurrentPage('detail');
  };

  const handlePageChange = (page: Page) => {
    setCurrentPage(page);
    if (page !== 'detail') {
      setStreamUrl(null);
      setSelectedSessionId(null);
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-primary)' }}>
      <Sidebar currentPage={currentPage === 'detail' ? 'sessions' : currentPage} onPageChange={handlePageChange} />
      
      <main style={{ 
        flex: 1, 
        marginLeft: 'var(--sidebar-width)',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {currentPage === 'home' && (
          <HomePage 
            onNewAnalysis={() => setIsModalOpen(true)} 
            onSessionClick={handleSessionClick} 
          />
        )}

        {currentPage === 'sessions' && (
          <SessionsPage onSessionClick={handleSessionClick} onRunImmediate={handleRunLive} />
        )}

        {currentPage === 'detail' && (
          <div className="fade-in" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <SessionDetailPage
              streamUrl={streamUrl}
              sessionId={selectedSessionId || undefined}
            />
          </div>
        )}

        {currentPage === 'topics' && <TopicsPage />}
        
        {currentPage === 'newsletter' && <NewsletterPage />}

        {currentPage === 'settings' && <SettingsPage />}

        {currentPage === 'sources' && (
          <div className="fade-in" style={{ padding: 'var(--spacing-xl)', textAlign: 'center', marginTop: '100px' }}>
            <h1 style={{ fontSize: '2rem', marginBottom: 'var(--spacing-md)' }}>Sources</h1>
            <p style={{ color: 'var(--text-secondary)' }}>La gestion globale des sources est en cours de développement.</p>
          </div>
        )}
      </main>

      <LiveRunModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onRun={handleRunLive} 
      />
    </div>
  );
}

export default App;
