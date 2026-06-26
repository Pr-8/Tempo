import React, { useState, useEffect } from 'react';
import AddTaskForm from './components/AddTaskForm';
import ScheduleView from './components/ScheduleView';
import ChatPanel from './components/ChatPanel';
import MemoryPanel from './components/MemoryPanel';
import CalendarSettings from './components/CalendarSettings';
import client from './api/client';

/* ── Error Boundary ──────────────────────────────────────── */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("App Error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100vh', background: 'var(--bg-base)', color: 'var(--text-primary)', gap: '16px'
        }}>
          <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', background: 'rgba(248,113,113,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <h1 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-semibold)' }}>
            Something went wrong
          </h1>
          <pre style={{
            padding: '16px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)',
            color: 'var(--danger)', fontSize: 'var(--font-size-sm)', maxWidth: '500px', overflow: 'auto'
          }}>
            {this.state.error?.toString()}
          </pre>
          <button
            onClick={() => window.location.reload()}
            className="btn-primary"
            style={{ marginTop: '8px' }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ── Priority Helpers ────────────────────────────────────── */
const priorityLabel = (p) => {
  if (p <= 2) return { text: 'Low', cls: 'badge-low' };
  if (p <= 3) return { text: 'Medium', cls: 'badge-medium' };
  return { text: 'High', cls: 'badge-high' };
};

const statusLabel = (s) => {
  if (s === 'completed') return '✓ Done';
  if (s === 'in_progress') return '◐ Active';
  return '○ Pending';
};

const formatDeadline = (d) => {
  if (!d) return '—';
  const dt = new Date(d);
  const now = new Date();
  const diff = Math.ceil((dt - now) / (1000 * 60 * 60 * 24));
  const dateStr = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  if (diff < 0) return `${dateStr} (overdue)`;
  if (diff === 0) return `${dateStr} (today)`;
  if (diff === 1) return `${dateStr} (tomorrow)`;
  if (diff <= 3) return `${dateStr} (${diff}d left)`;
  return dateStr;
};

/* ── Main App ────────────────────────────────────────────── */
function App() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);

  /* WebSocket for Real-time updates */
  useEffect(() => {
    const connectWS = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname;
      const port = '8000';
      const wsUrl = `${protocol}//${host}:${port}/ws`;
      const ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        if (event.data === 'REFRESH') {
          setRefreshTrigger(prev => prev + 1);
        }
      };

      ws.onclose = () => {
        setTimeout(connectWS, 3000);
      };

      return ws;
    };

    const socket = connectWS();
    return () => {
      socket.onclose = null;
      socket.close();
    };
  }, []);

  const fetchTasks = async () => {
    try {
      const res = await client.get('/api/tasks/');
      setTasks(res.data);
    } catch (err) {
      console.error('Error fetching tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [refreshTrigger]);

  const handleTaskAdded = () => {
    fetchTasks();
    setRefreshTrigger(prev => prev + 1);
  };

  const handleClearAllTasks = async () => {
    if (window.confirm("Are you sure you want to delete all tasks and clear your schedule? This action cannot be undone.")) {
      try {
        await client.delete('/api/tasks/');
        fetchTasks();
        setRefreshTrigger(prev => prev + 1);
      } catch (err) {
        alert("Error clearing tasks: " + (err.response?.data?.detail || err.message));
      }
    }
  };

  const handleReschedule = async () => {
    try {
      await client.post('/api/sessions/reschedule');
      setRefreshTrigger(prev => prev + 1);
    } catch (err) {
      alert('Error during reschedule');
    }
  };

  const handleDeleteTask = async (id) => {
    if (window.confirm('Delete this task?')) {
      try {
        await client.delete(`/api/tasks/${id}`);
        setRefreshTrigger(prev => prev + 1);
      } catch (err) {
        alert('Error deleting task');
      }
    }
  };

  /* Loading state */
  if (loading) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: 'var(--bg-base)', gap: '20px'
      }}>
        <div style={{
          fontSize: '40px', fontWeight: 'var(--font-weight-bold)',
          background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent', backgroundClip: 'text',
        }}>
          Tempo
        </div>
        <div className="loading-spinner" />
        <div style={{ color: 'var(--text-tertiary)', fontSize: 'var(--font-size-sm)' }}>
          Loading your schedule...
        </div>
      </div>
    );
  }

  const activeTasks = Array.isArray(tasks) ? tasks.filter(t => t.status !== 'completed') : [];
  const completedTasks = Array.isArray(tasks) ? tasks.filter(t => t.status === 'completed') : [];

  return (
    <div style={{
      display: 'flex', height: '100vh', background: 'var(--bg-base)',
      overflow: 'hidden'
    }}>

      {/* ─── Left Sidebar ─── */}
      <aside style={{
        width: sidebarCollapsed ? '60px' : '320px',
        minWidth: sidebarCollapsed ? '60px' : '320px',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex', flexDirection: 'column',
        transition: 'width var(--transition-base), min-width var(--transition-base)',
        overflow: 'hidden',
      }}>

        {/* Sidebar header */}
        <div style={{
          padding: sidebarCollapsed ? '0 12px' : '0 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
          height: '56px',
        }}>
          {!sidebarCollapsed && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '32px', height: '32px', borderRadius: 'var(--radius-md)',
                background: 'var(--accent-gradient)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '16px', fontWeight: 'var(--font-weight-bold)',
                color: 'white'
              }}>T</div>
              <span style={{
                fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-bold)',
                background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent', backgroundClip: 'text'
              }}>Tempo</span>
            </div>
          )}
          <button
            className="btn-icon"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            style={{ flexShrink: 0 }}
          >
            {sidebarCollapsed ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            )}
          </button>
        </div>

        {!sidebarCollapsed && (
          <>
            {/* Add Task Form */}
            <div style={{ padding: '20px 20px 0', flexShrink: 0 }}>
              <AddTaskForm onTaskAdded={handleTaskAdded} />
            </div>

            {/* Task List */}
            <div style={{
              flex: 1, overflowY: 'auto', padding: '20px',
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: '14px'
              }}>
                <h2 style={{
                  fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--text-secondary)', textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                }}>
                  Tasks ({activeTasks.length})
                </h2>
                {tasks.length > 0 && (
                  <button
                    onClick={handleClearAllTasks}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-tertiary)',
                      fontSize: 'var(--font-size-xs)',
                      fontWeight: 'var(--font-weight-medium)',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      borderRadius: 'var(--radius-sm)',
                      transition: 'color var(--transition-fast), background var(--transition-fast)',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.color = 'var(--danger)';
                      e.currentTarget.style.background = 'rgba(248, 113, 113, 0.08)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.color = 'var(--text-tertiary)';
                      e.currentTarget.style.background = 'none';
                    }}
                  >
                    Clear All
                  </button>
                )}
              </div>

              {activeTasks.length > 0 ? activeTasks.map((task, i) => {
                const pr = priorityLabel(task.priority);
                const deadlineStr = formatDeadline(task.deadline);
                const isOverdue = deadlineStr.includes('overdue');
                return (
                  <div key={task.id} style={{
                    padding: '14px', marginBottom: '8px',
                    background: 'var(--bg-elevated)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    position: 'relative',
                    animation: `fade-in 0.3s ease ${i * 0.04}s both`,
                    transition: 'border-color var(--transition-fast), background var(--transition-fast)',
                    cursor: 'default',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = 'var(--border-strong)';
                    e.currentTarget.style.background = 'var(--glass-bg)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = 'var(--border-subtle)';
                    e.currentTarget.style.background = 'var(--bg-elevated)';
                  }}
                  >
                    <div style={{
                      display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                      gap: '8px'
                    }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontWeight: 'var(--font-weight-medium)',
                          fontSize: 'var(--font-size-sm)',
                          color: 'var(--text-primary)',
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>
                          {task.title}
                        </div>
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: '8px',
                          marginTop: '6px', flexWrap: 'wrap',
                        }}>
                          <span className={`badge ${pr.cls}`}>{pr.text}</span>
                          <span style={{
                            fontSize: 'var(--font-size-xs)',
                            color: isOverdue ? 'var(--danger)' : 'var(--text-tertiary)',
                          }}>
                            {deadlineStr}
                          </span>
                        </div>
                        {task.course && (
                          <div style={{
                            fontSize: 'var(--font-size-xs)', color: 'var(--text-tertiary)',
                            marginTop: '4px',
                          }}>
                            {task.course}
                          </div>
                        )}
                      </div>
                      <button
                        className="btn-icon"
                        onClick={() => handleDeleteTask(task.id)}
                        title="Delete task"
                        style={{ color: 'var(--text-tertiary)', fontSize: '14px', flexShrink: 0 }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                );
              }) : (
                <div style={{
                  textAlign: 'center', padding: '30px 20px',
                  color: 'var(--text-tertiary)', fontSize: 'var(--font-size-sm)'
                }}>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5 }}><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>
                  No active tasks yet
                </div>
              )}

              {/* Completed tasks section */}
              {completedTasks.length > 0 && (
                <div style={{ marginTop: '20px' }}>
                  <div style={{
                    fontSize: 'var(--font-size-xs)', fontWeight: 'var(--font-weight-medium)',
                    color: 'var(--text-tertiary)', textTransform: 'uppercase',
                    letterSpacing: '0.08em', marginBottom: '10px'
                  }}>
                    Completed ({completedTasks.length})
                  </div>
                  {completedTasks.slice(0, 5).map(task => (
                    <div key={task.id} style={{
                      padding: '10px 14px', marginBottom: '4px',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      opacity: 0.5,
                    }}>
                      <span style={{
                        fontSize: 'var(--font-size-sm)', color: 'var(--text-tertiary)',
                        textDecoration: 'line-through',
                      }}>
                        {task.title}
                      </span>
                      <button
                        className="btn-icon"
                        onClick={() => handleDeleteTask(task.id)}
                        style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Memory Panel */}
              <div style={{ marginTop: '20px' }}>
                <MemoryPanel />
              </div>

              {/* Calendar Settings */}
              <CalendarSettings />
            </div>
          </>
        )}
      </aside>

      {/* ─── Main Content: Calendar ─── */}
      <main style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Top bar */}
        <div style={{
          padding: '0 28px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
          background: 'var(--bg-surface)',
          height: '56px',
        }}>
          <div style={{
            fontSize: 'var(--font-size-sm)', color: 'var(--text-secondary)',
          }}>
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              className="btn-ghost"
              onClick={handleReschedule}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                fontSize: 'var(--font-size-sm)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              Reschedule
            </button>
            <button
              className="btn-icon"
              onClick={() => setChatOpen(!chatOpen)}
              title={chatOpen ? 'Close chat' : 'Open chat'}
              style={{
                fontSize: '18px',
                color: chatOpen ? 'var(--accent-primary)' : 'var(--text-tertiary)',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            </button>
          </div>
        </div>

        {/* Calendar */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          <ScheduleView refreshTrigger={refreshTrigger} />
        </div>
      </main>

      {/* ─── Right Panel: Chat ─── */}
      {chatOpen && <ChatPanel />}
    </div>
  );
}

export default function Root() {
  return (
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  );
}
