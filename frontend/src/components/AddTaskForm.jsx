import React, { useState } from 'react';
import client from '../api/client';

/* ── scoped styles ──────────────────────────────────────── */
const styles = `
  /* ── Container ── */
  .atf-container {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    display: flex;
    flex-direction: column;
    gap: 14px;
    animation: atf-fade-in 0.35s ease-out both;
  }

  @keyframes atf-fade-in {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  /* ── Heading ── */
  .atf-heading {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }
  .atf-heading-icon {
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: var(--font-weight-bold);
  }

  /* ── Toggle ── */
  .atf-toggle-track {
    position: relative;
    display: flex;
    background: var(--bg-elevated);
    border-radius: var(--radius-full);
    overflow: hidden;
    border: 1px solid var(--border-subtle);
  }
  .atf-toggle-slider {
    position: absolute;
    top: 3px; bottom: 3px;
    width: calc(50% - 3px);
    border-radius: var(--radius-full);
    background: var(--accent-gradient);
    transition: left var(--transition-base);
    box-shadow: var(--shadow-glow);
    pointer-events: none;
    z-index: 0;
  }
  .atf-toggle-slider[data-active="task"]  { left: 3px; }
  .atf-toggle-slider[data-active="event"] { left: calc(50%); }

  .atf-toggle-btn {
    position: relative;
    z-index: 1;
    flex: 1;
    padding: 9px 0;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    font-family: var(--font-family);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: color var(--transition-fast);
    text-align: center;
  }
  .atf-toggle-btn[data-selected="true"] {
    color: #fff;
    font-weight: var(--font-weight-semibold);
  }

  /* ── Labels ── */
  .atf-label {
    display: block;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 5px;
  }

  /* ── Field Group ── */
  .atf-field {
    display: flex;
    flex-direction: column;
  }

  .atf-row {
    display: flex;
    gap: 10px;
  }
  .atf-row > .atf-field { flex: 1; min-width: 0; }
  .atf-row > .atf-field-2x { flex: 2; min-width: 0; }

  /* ── Priority Pills ── */
  .atf-priority-group {
    display: flex;
    gap: 6px;
  }
  .atf-priority-pill {
    flex: 1;
    padding: 8px 0;
    border-radius: var(--radius-full);
    border: 1px solid var(--border-subtle);
    background: var(--bg-base);
    color: var(--text-secondary);
    font-family: var(--font-family);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-align: center;
  }
  .atf-priority-pill:hover {
    border-color: var(--border-strong);
    color: var(--text-primary);
  }
  .atf-priority-pill[data-selected="true"][data-level="low"] {
    background: rgba(52, 211, 153, 0.12);
    border-color: var(--priority-low);
    color: var(--priority-low);
  }
  .atf-priority-pill[data-selected="true"][data-level="medium"] {
    background: rgba(251, 191, 36, 0.12);
    border-color: var(--priority-medium);
    color: var(--priority-medium);
  }
  .atf-priority-pill[data-selected="true"][data-level="high"] {
    background: rgba(248, 113, 113, 0.12);
    border-color: var(--priority-high);
    color: var(--priority-high);
  }

  /* ── Collapsible draft-time ── */
  .atf-collapse-trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: none;
    border: none;
    color: var(--text-tertiary);
    font-family: var(--font-family);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    padding: 0;
    transition: color var(--transition-fast);
  }
  .atf-collapse-trigger:hover { color: var(--text-secondary); }
  .atf-collapse-chevron {
    display: inline-block;
    transition: transform var(--transition-fast);
    font-size: 10px;
  }
  .atf-collapse-chevron[data-open="true"] { transform: rotate(90deg); }

  .atf-collapse-body {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows var(--transition-base);
  }
  .atf-collapse-body[data-open="true"] {
    grid-template-rows: 1fr;
  }
  .atf-collapse-inner {
    overflow: hidden;
  }
  .atf-collapse-inner > .atf-row {
    padding-top: 10px;
  }

  /* ── Submit Button ── */
  .atf-submit {
    width: 100%;
    padding: 12px 0;
    border: none;
    border-radius: var(--radius-md);
    background: var(--accent-gradient);
    color: #fff;
    font-family: var(--font-family);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    cursor: pointer;
    transition: all var(--transition-fast);
    box-shadow: var(--shadow-sm);
    letter-spacing: 0.02em;
    margin-top: 4px;
  }
  .atf-submit:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow), var(--shadow-md);
  }
  .atf-submit:active {
    transform: translateY(0);
  }
`;

/* ── component ──────────────────────────────────────────── */
export default function AddTaskForm({ onTaskAdded }) {
  const [type, setType] = useState('task');
  const [draftOpen, setDraftOpen] = useState(false);
  const [startD, setStartD] = useState('');
  const [startT, setStartT] = useState('');
  const [endD, setEndD] = useState('');
  const [endT, setEndT] = useState('');

  const [formData, setFormData] = useState({
    title: '',
    course: '',
    estimated_hours: '',
    deadline: '',
    priority: 'medium',
    fixed_start: '',
    fixed_end: ''
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const priorityMap = { low: 1, medium: 3, high: 5 };
      const payload = {
        title: formData.title,
        course: formData.course,
        priority: priorityMap[formData.priority] || 3,
        is_fixed: type === 'event',
      };

      const combinedStart = startD && startT ? `${startD}T${startT}` : '';
      const combinedEnd = endD && endT ? `${endD}T${endT}` : '';

      if (type === 'event') {
        payload.fixed_start = combinedStart;
        payload.fixed_end = combinedEnd;
        payload.estimated_hours = 1.0;
        payload.deadline = combinedEnd;
      } else {
        payload.estimated_hours = parseFloat(formData.estimated_hours);
        payload.deadline = formData.deadline + 'T23:59:59';
        if (combinedStart && combinedEnd) {
          payload.fixed_start = combinedStart;
          payload.fixed_end = combinedEnd;
        }
      }

      await client.post('/api/tasks/', payload);
      setFormData({
        title: '',
        course: '',
        estimated_hours: '',
        deadline: '',
        priority: 'medium',
        fixed_start: '',
        fixed_end: ''
      });
      setStartD('');
      setStartT('');
      setEndD('');
      setEndT('');
      if (onTaskAdded) onTaskAdded();
    } catch (err) {
      alert('Error adding: ' + (err.response?.data?.detail || err.message));
    }
  };

  const set = (key) => (e) =>
    setFormData({ ...formData, [key]: e.target.value });

  return (
    <>
      <style>{styles}</style>

      <form onSubmit={handleSubmit} className="atf-container">
        {/* ── heading ── */}
        <h3 className="atf-heading">
          <span className="atf-heading-icon">+</span>
          {type === 'task' ? 'New Task' : 'New Event'}
        </h3>

        {/* ── toggle ── */}
        <div className="atf-toggle-track">
          <div className="atf-toggle-slider" data-active={type} />
          <button
            type="button"
            className="atf-toggle-btn"
            data-selected={type === 'task'}
            onClick={() => setType('task')}
          >
            Task
          </button>
          <button
            type="button"
            className="atf-toggle-btn"
            data-selected={type === 'event'}
            onClick={() => setType('event')}
          >
            Event
          </button>
        </div>

        {/* ── title ── */}
        <div className="atf-field">
          <label className="atf-label">Title</label>
          <input
            placeholder="e.g. Calculus Prep"
            value={formData.title}
            onChange={set('title')}
            required
          />
        </div>

        {/* ── course ── */}
        <div className="atf-field">
          <label className="atf-label">Course (optional)</label>
          <input
            placeholder="e.g. MATH 201"
            value={formData.course}
            onChange={set('course')}
          />
        </div>

        {/* ── task-specific fields ── */}
        {type === 'task' ? (
          <>
            <div className="atf-row">
              <div className="atf-field">
                <label className="atf-label">Est. Hours</label>
                <input
                  type="number"
                  step="0.5"
                  placeholder="2.5"
                  value={formData.estimated_hours}
                  onChange={set('estimated_hours')}
                  required
                />
              </div>
              <div className="atf-field atf-field-2x">
                <label className="atf-label">Deadline</label>
                <input
                  type="date"
                  value={formData.deadline}
                  onChange={set('deadline')}
                  required
                />
              </div>
            </div>

            {/* collapsible draft time */}
            <div>
              <button
                type="button"
                className="atf-collapse-trigger"
                onClick={() => setDraftOpen((o) => !o)}
              >
                <span
                  className="atf-collapse-chevron"
                  data-open={draftOpen}
                >
                  ›
                </span>
                Set a draft time (AI can move this later)
              </button>

              <div className="atf-collapse-body" data-open={draftOpen}>
                <div className="atf-collapse-inner">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '10px' }}>
                    <div className="atf-row">
                      <div className="atf-field" style={{ flex: 3 }}>
                        <label className="atf-label">Start Date</label>
                        <input
                          type="date"
                          value={startD}
                          onChange={(e) => setStartD(e.target.value)}
                        />
                      </div>
                      <div className="atf-field" style={{ flex: 2 }}>
                        <label className="atf-label">Time</label>
                        <input
                          type="time"
                          value={startT}
                          onChange={(e) => setStartT(e.target.value)}
                        />
                      </div>
                    </div>
                    <div className="atf-row">
                      <div className="atf-field" style={{ flex: 3 }}>
                        <label className="atf-label">End Date</label>
                        <input
                          type="date"
                          value={endD}
                          onChange={(e) => setEndD(e.target.value)}
                        />
                      </div>
                      <div className="atf-field" style={{ flex: 2 }}>
                        <label className="atf-label">Time</label>
                        <input
                          type="time"
                          value={endT}
                          onChange={(e) => setEndT(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : (
          /* ── event-specific fields ── */
          <>
            <div className="atf-row">
              <div className="atf-field" style={{ flex: 3 }}>
                <label className="atf-label">Start Date</label>
                <input
                  type="date"
                  value={startD}
                  onChange={(e) => setStartD(e.target.value)}
                  required
                />
              </div>
              <div className="atf-field" style={{ flex: 2 }}>
                <label className="atf-label">Time</label>
                <input
                  type="time"
                  value={startT}
                  onChange={(e) => setStartT(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="atf-row">
              <div className="atf-field" style={{ flex: 3 }}>
                <label className="atf-label">End Date</label>
                <input
                  type="date"
                  value={endD}
                  onChange={(e) => setEndD(e.target.value)}
                  required
                />
              </div>
              <div className="atf-field" style={{ flex: 2 }}>
                <label className="atf-label">Time</label>
                <input
                  type="time"
                  value={endT}
                  onChange={(e) => setEndT(e.target.value)}
                  required
                />
              </div>
            </div>
          </>
        )}

        {/* ── priority ── */}
        <div className="atf-field">
          <label className="atf-label">Priority</label>
          <div className="atf-priority-group">
            {['low', 'medium', 'high'].map((level) => (
              <button
                key={level}
                type="button"
                className="atf-priority-pill"
                data-level={level}
                data-selected={formData.priority === level}
                onClick={() =>
                  setFormData({ ...formData, priority: level })
                }
              >
                {level === 'low' ? 'Low' : level === 'medium' ? 'Med' : 'High'}
              </button>
            ))}
          </div>
        </div>

        {/* ── submit ── */}
        <button type="submit" className="atf-submit">
          Save {type === 'task' ? 'Task' : 'Event'}
        </button>
      </form>
    </>
  );
}
