import React, { useState, useEffect } from 'react';
import client from '../api/client';

const styles = `
  .cal-container {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: var(--space-md);
    font-family: var(--font-family);
    transition: all var(--transition-base);
  }

  .cal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }

  .cal-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-primary);
    font-weight: var(--font-weight-semibold);
    font-size: var(--font-size-sm);
  }

  .cal-chevron {
    display: inline-block;
    transition: transform var(--transition-fast);
    font-size: 10px;
    color: var(--text-tertiary);
  }

  .cal-chevron[data-open="true"] {
    transform: rotate(90deg);
  }

  .cal-collapse-body {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows var(--transition-base);
  }

  .cal-collapse-body[data-open="true"] {
    grid-template-rows: 1fr;
  }

  .cal-collapse-inner {
    overflow: hidden;
  }

  .cal-content {
    margin-top: var(--space-md);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .cal-status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--font-size-xs);
  }

  .cal-indicator {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
  }

  .cal-indicator.connected {
    background: #10b981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
  }

  .cal-indicator.disconnected {
    background: var(--text-tertiary);
  }

  .cal-text-connected {
    color: var(--text-primary);
    font-weight: var(--font-weight-medium);
  }

  .cal-text-disconnected {
    color: var(--text-tertiary);
  }

  .cal-info {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
    line-height: 1.4;
  }

  .cal-sync-time {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
  }

  .cal-btn-group {
    display: flex;
    gap: 8px;
  }

  .cal-btn-connect {
    width: 100%;
    background: #4285f4;
    color: white;
    border: none;
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: background var(--transition-fast);
  }

  .cal-btn-connect:hover {
    background: #357ae8;
  }

  .cal-btn-sync {
    flex: 1;
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .cal-btn-sync:hover:not(:disabled) {
    border-color: var(--border-strong);
    background: var(--glass-bg);
  }

  .cal-btn-sync:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .cal-btn-disconnect {
    background: none;
    border: 1px solid rgba(248, 113, 113, 0.3);
    color: var(--danger);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .cal-btn-disconnect:hover {
    background: rgba(248, 113, 113, 0.08);
    border-color: var(--danger);
  }
`;

export default function CalendarSettings({ onConnectionChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState({ connected: false, last_synced_at: null });
  const [syncing, setSyncing] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await client.get('/api/calendar/status');
      setStatus(res.data);
      if (onConnectionChange) {
        onConnectionChange(res.data.connected);
      }
    } catch (err) {
      console.error('Failed to fetch calendar status:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleConnect = async () => {
    try {
      const res = await client.get('/api/calendar/auth-url');
      const width = 500;
      const height = 650;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        res.data.url,
        'google-calendar-oauth',
        `width=${width},height=${height},left=${left},top=${top}`
      );

      if (!popup) {
        alert('Popup blocker active. Please allow popups for this site.');
        return;
      }

      const handleMessage = (event) => {
        if (event.data === 'gcal_connected') {
          fetchStatus();
          window.removeEventListener('message', handleMessage);
        } else if (event.data === 'gcal_failed') {
          alert('Failed to connect Google Calendar.');
          window.removeEventListener('message', handleMessage);
        }
      };

      window.addEventListener('message', handleMessage);
    } catch (err) {
      alert('Failed to initialize OAuth connection.');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await client.post('/api/calendar/sync');
      fetchStatus();
      alert(`Sync successful! Imported ${res.data.synced_events} events.`);
    } catch (err) {
      alert('Sync failed.');
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    if (window.confirm('Disconnect Google Calendar? This will remove all Tempo study sessions from your calendar.')) {
      try {
        await client.post('/api/calendar/disconnect');
        fetchStatus();
      } catch (err) {
        alert('Failed to disconnect.');
      }
    }
  };

  const formatLastSynced = (dateStr) => {
    if (!dateStr) return 'Never';
    const dt = new Date(dateStr);
    return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + dt.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <>
      <style>{styles}</style>
      <div className="cal-container" style={{ marginTop: '12px' }}>
        <div className="cal-header" onClick={() => setIsOpen(!isOpen)}>
          <div className="cal-header-left">
            <span className="cal-chevron" data-open={isOpen}>▶</span>
            <span>Google Calendar</span>
          </div>
        </div>

        <div className="cal-collapse-body" data-open={isOpen}>
          <div className="cal-collapse-inner">
            <div className="cal-content">
              <div className="cal-status-row">
                <div className={`cal-indicator ${status.connected ? 'connected' : 'disconnected'}`} />
                {status.connected ? (
                  <span className="cal-text-connected">Connected</span>
                ) : (
                  <span className="cal-text-disconnected">Disconnected</span>
                )}
              </div>

              {status.connected ? (
                <>
                  <div className="cal-sync-time">
                    Last synced: {formatLastSynced(status.last_synced_at)}
                  </div>
                  <div className="cal-btn-group">
                    <button 
                      className="cal-btn-sync" 
                      onClick={handleSync}
                      disabled={syncing}
                    >
                      {syncing ? 'Syncing...' : 'Sync Now'}
                    </button>
                    <button className="cal-btn-disconnect" onClick={handleDisconnect}>
                      Disconnect
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="cal-info">
                    Sync your study sessions to your calendar and automatically block busy slots.
                  </div>
                  <button className="cal-btn-connect" onClick={handleConnect}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12.24 10.285V13.4h6.887C18.2 15.614 15.645 18 12.24 18c-3.86 0-7-3.14-7-7s3.14-7 7-7c1.8 0 3.42.68 4.67 1.8l3.18-3.18C17.97 1.7 15.28 1 12.24 1c-5.52 0-10 4.48-10 10s4.48 10 10 10c5.78 0 9.61-4.06 9.61-9.78 0-.66-.06-1.29-.17-1.936H12.24z"/>
                    </svg>
                    Connect Google Calendar
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
