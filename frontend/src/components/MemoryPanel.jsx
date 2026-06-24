import React, { useState, useEffect } from 'react';
import client from '../api/client';

const styles = `
  .mem-container {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: var(--space-md);
    font-family: var(--font-family);
    transition: all var(--transition-base);
  }

  .mem-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }

  .mem-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-primary);
    font-weight: var(--font-weight-semibold);
    font-size: var(--font-size-sm);
  }

  .mem-count-badge {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    padding: 2px 8px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--text-secondary);
  }

  .mem-chevron {
    display: inline-block;
    transition: transform var(--transition-fast);
    font-size: 10px;
    color: var(--text-tertiary);
  }

  .mem-chevron[data-open="true"] {
    transform: rotate(90deg);
  }

  .mem-clear-btn {
    background: none;
    border: none;
    color: var(--danger);
    font-family: var(--font-family);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    cursor: pointer;
    padding: 0;
    transition: opacity var(--transition-fast);
  }

  .mem-clear-btn:hover {
    opacity: 0.8;
  }

  .mem-collapse-body {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows var(--transition-base);
  }

  .mem-collapse-body[data-open="true"] {
    grid-template-rows: 1fr;
  }

  .mem-collapse-inner {
    overflow: hidden;
  }

  .mem-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 250px;
    overflow-y: auto;
    margin-top: var(--space-md);
    padding-right: 4px;
  }

  .mem-list::-webkit-scrollbar {
    width: 4px;
  }

  .mem-list::-webkit-scrollbar-track {
    background: transparent;
  }

  .mem-list::-webkit-scrollbar-thumb {
    background: var(--border-strong);
    border-radius: var(--radius-full);
  }

  .mem-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-sm);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-sm) var(--space-md);
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    line-height: 1.4;
    transition: border-color var(--transition-fast), background var(--transition-fast);
  }

  .mem-item:hover {
    border-color: var(--border-strong);
    background: var(--bg-elevated);
  }

  .mem-delete-btn {
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    font-size: 14px;
    padding: 0 2px;
    line-height: 1;
    transition: color var(--transition-fast);
    flex-shrink: 0;
    margin-top: 1px;
  }

  .mem-delete-btn:hover {
    color: var(--danger);
  }

  .mem-empty {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
    text-align: center;
    padding: var(--space-md) 0 0;
  }
`;

export default function MemoryPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [memories, setMemories] = useState([]);

  const fetchMemories = async () => {
    try {
      const response = await client.get('/api/memories/');
      setMemories(response.data);
    } catch (err) {
      console.error('Failed to fetch memories:', err);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, []);

  const handleDelete = async (id) => {
    try {
      await client.delete(`/api/memories/${id}`);
      setMemories(prev => prev.filter(m => m.id !== id));
    } catch (err) {
      console.error('Failed to delete memory:', err);
    }
  };

  const handleClearAll = async (e) => {
    e.stopPropagation(); // Avoid toggling collapse when clicking Clear All
    if (window.confirm('Are you sure you want to clear all user memories? This action cannot be undone.')) {
      try {
        await client.delete('/api/memories/');
        setMemories([]);
      } catch (err) {
        console.error('Failed to clear memories:', err);
      }
    }
  };

  return (
    <>
      <style>{styles}</style>
      <div className="mem-container">
        <div className="mem-header" onClick={() => setIsOpen(!isOpen)}>
          <div className="mem-header-left">
            <span className="mem-chevron" data-open={isOpen}>▶</span>
            <span>Memories</span>
            <span className="mem-count-badge">{memories.length}</span>
          </div>
          {memories.length > 0 && (
            <button className="mem-clear-btn" onClick={handleClearAll}>
              Clear All
            </button>
          )}
        </div>

        <div className="mem-collapse-body" data-open={isOpen}>
          <div className="mem-collapse-inner">
            {memories.length === 0 ? (
              <div className="mem-empty">No memories saved yet</div>
            ) : (
              <div className="mem-list">
                {memories.map(m => (
                  <div key={m.id} className="mem-item">
                    <span>{m.content}</span>
                    <button 
                      className="mem-delete-btn" 
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(m.id);
                      }}
                      title="Delete memory"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
