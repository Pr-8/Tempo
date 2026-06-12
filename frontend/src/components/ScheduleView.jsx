import React, { useState, useEffect } from 'react';
import FullCalendar from '@fullcalendar/react';
import timeGridPlugin from '@fullcalendar/timegrid';
import dayGridPlugin from '@fullcalendar/daygrid';
import client from '../api/client';

const priorityColors = {
  1: '#34d399',
  2: '#34d399',
  3: '#fbbf24',
  4: '#f87171',
  5: '#f87171'
};

const priorityLabels = {
  1: 'Low',
  2: 'Low',
  3: 'Medium',
  4: 'High',
  5: 'High'
};

const renderMarkdown = (text) => {
  if (!text) return null;
  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    const bulletMatch = line.match(/^\s*[\*\-]\s+(.*)/);

    const parseInline = (content) => {
      const parts = content.split(/(\*\*[^*]+?\*\*)/g);
      return parts.map((part, partIdx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={partIdx}>{part.slice(2, -2)}</strong>;
        }
        const italicParts = part.split(/(\*[^*]+?\*)/g);
        return italicParts.map((ip, ipIdx) => {
          if (ip.startsWith('*') && ip.endsWith('*')) {
            return <em key={ipIdx}>{ip.slice(1, -1)}</em>;
          }
          return ip;
        });
      });
    };

    if (bulletMatch) {
      return (
        <div
          key={lineIdx}
          style={{
            display: 'list-item',
            listStyleType: 'disc',
            marginLeft: '18px',
            marginTop: '3px',
            marginBottom: '3px'
          }}
        >
          {parseInline(bulletMatch[1])}
        </div>
      );
    }

    return (
      <p
        key={lineIdx}
        style={{
          margin: '4px 0',
          minHeight: line.trim() === '' ? '8px' : 'auto'
        }}
      >
        {parseInline(line)}
      </p>
    );
  });
};

/* ── Inline style objects ─────────────────────────────────── */

const wrapperStyle = {
  padding: 'var(--space-lg)',
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--space-md)',
};

const coachBoxStyle = {
  background: 'var(--glass-bg)',
  backdropFilter: 'blur(var(--glass-blur))',
  WebkitBackdropFilter: 'blur(var(--glass-blur))',
  border: '1px solid var(--glass-border)',
  borderRadius: 'var(--radius-lg)',
  padding: 'var(--space-md) var(--space-lg)',
  position: 'relative',
  overflow: 'hidden',
};

const coachAccentBarStyle = {
  position: 'absolute',
  left: 0,
  top: 0,
  bottom: 0,
  width: '3px',
  background: 'var(--accent-gradient)',
  borderRadius: '3px 0 0 3px',
};

const coachHeaderStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--space-sm)',
  marginBottom: 'var(--space-xs)',
};

const coachIconStyle = {
  width: '28px',
  height: '28px',
  borderRadius: 'var(--radius-full)',
  background: 'var(--accent-primary-glow)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '14px',
  flexShrink: 0,
};

const coachLabelStyle = {
  fontSize: 'var(--font-size-sm)',
  fontWeight: 'var(--font-weight-semibold)',
  color: 'var(--accent-secondary)',
  letterSpacing: '0.03em',
  textTransform: 'uppercase',
};

const coachTextStyle = {
  margin: 0,
  fontSize: 'var(--font-size-sm)',
  color: 'var(--text-secondary)',
  lineHeight: 1.6,
  paddingLeft: '36px',
};

const calendarWrapperStyle = {
  borderRadius: 'var(--radius-lg)',
  overflow: 'hidden',
  background: 'var(--bg-surface)',
  border: '1px solid var(--border-subtle)',
  boxShadow: 'var(--shadow-md)',
};

/* ── Event content styles ─────────────────────────────────── */

const eventContainerStyle = {
  padding: '2px 0',
  fontSize: 'var(--font-size-xs)',
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
  height: '100%',
};

const eventHeaderStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
};

const eventDotStyle = (color) => ({
  width: '7px',
  height: '7px',
  borderRadius: 'var(--radius-full)',
  backgroundColor: color,
  flexShrink: 0,
  boxShadow: `0 0 6px ${color}40`,
});

const eventTitleStyle = {
  fontWeight: 'var(--font-weight-semibold)',
  color: '#fff',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: 1.3,
};

const eventCourseStyle = {
  fontSize: '10px',
  color: 'rgba(255,255,255,0.7)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const eventActionsStyle = {
  display: 'flex',
  gap: '4px',
  marginTop: 'auto',
  paddingTop: '2px',
};

const pillButtonBase = {
  fontSize: '9px',
  fontWeight: 'var(--font-weight-semibold)',
  fontFamily: 'var(--font-family)',
  padding: '1px 6px',
  borderRadius: 'var(--radius-full)',
  border: '1px solid transparent',
  cursor: 'pointer',
  transition: 'all 150ms cubic-bezier(0.4, 0, 0.2, 1)',
  lineHeight: 1.4,
  letterSpacing: '0.02em',
  whiteSpace: 'nowrap',
};

const donePillStyle = {
  ...pillButtonBase,
  background: 'var(--bg-surface)',
  color: '#34d399',
  borderColor: 'rgba(52, 211, 153, 0.25)',
};

const failedPillStyle = {
  ...pillButtonBase,
  background: 'var(--bg-surface)',
  color: '#f87171',
  borderColor: 'rgba(248, 113, 113, 0.25)',
};

/* ── Component ────────────────────────────────────────────── */

export default function ScheduleView({ refreshTrigger }) {
  const [sessions, setSessions] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [prefs, setPrefs] = useState(null);
  const [hoveredBtn, setHoveredBtn] = useState(null);

  const fetchData = async () => {
    try {
      const [sessionsRes, tasksRes, prefsRes] = await Promise.allSettled([
        client.get('/api/sessions/'),
        client.get('/api/tasks/'),
        client.get('/api/preferences/')
      ]);

      if (sessionsRes.status === 'fulfilled') setSessions(sessionsRes.value.data);
      if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value.data);
      if (prefsRes.status === 'fulfilled') setPrefs(prefsRes.value.data);

    } catch (err) {
      console.error('Error fetching data:', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, [refreshTrigger]);

  const handleComplete = async (id) => {
    try {
      await client.patch(`/api/sessions/${id}/complete`);
      fetchData();
    } catch (err) {
      alert('Error completing session');
    }
  };

  const handleFailed = async (id) => {
    try {
      await client.patch(`/api/sessions/${id}/failed`);
      setTimeout(fetchData, 2000);
    } catch (err) {
      alert('Error marking session failed');
    }
  };

  const taskMap = Array.isArray(tasks) ? Object.fromEntries(tasks.map(t => [t.id, t])) : {};
  const events = Array.isArray(sessions) ? sessions
    .filter(s => s && s.status === 'scheduled')
    .map(s => {
      const task = taskMap[s.task_id];
      return {
        id: s.id,
        title: task?.title || 'Study Session',
        start: s.start_time ? new Date(s.start_time) : new Date(),
        end: s.end_time ? new Date(s.end_time) : new Date(),
        backgroundColor: priorityColors[task?.priority] || '#7c5cfc',
        borderColor: 'transparent',
        extendedProps: { session: s, task: task }
      };
    }) : [];

  return (
    <div style={wrapperStyle}>
      {/* ── Coach Explanation (glassmorphism) ── */}
      {prefs?.last_schedule_explanation && (
        <div style={coachBoxStyle} className="glass">
          <div style={coachAccentBarStyle} />
          <div style={coachHeaderStyle}>
            <div style={coachIconStyle}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent-secondary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
              </svg>
            </div>
            <span style={coachLabelStyle}>Coach Says</span>
          </div>
          <div style={coachTextStyle}>{renderMarkdown(prefs.last_schedule_explanation)}</div>
        </div>
      )}

      {/* ── Calendar ── */}
      <div style={calendarWrapperStyle}>
        <FullCalendar
          plugins={[timeGridPlugin, dayGridPlugin]}
          initialView="timeGridWeek"
          nowIndicator={true}
          events={events}
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'timeGridWeek,timeGridDay'
          }}
          slotMinTime="07:00:00"
          slotMaxTime="22:00:00"
          scrollTime="08:00:00"
          allDaySlot={false}
          height="calc(100vh - 120px)"
          eventContent={(eventInfo) => {
            const { task, session } = eventInfo.event.extendedProps;
            const color = priorityColors[task?.priority] || '#7c5cfc';
            const doneKey = `done-${session?.id}`;
            const failKey = `fail-${session?.id}`;

            return (
              <div style={eventContainerStyle}>
                {/* Title row */}
                <div style={eventHeaderStyle}>
                  <span style={eventDotStyle(color)} />
                  <span style={eventTitleStyle}>{eventInfo.event.title}</span>
                </div>

                {/* Course subtitle */}
                {task?.course && (
                  <div style={eventCourseStyle}>{task.course}</div>
                )}

                {/* Action pills */}
                <div style={eventActionsStyle}>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleComplete(session.id); }}
                    onMouseEnter={() => setHoveredBtn(doneKey)}
                    onMouseLeave={() => setHoveredBtn(null)}
                    style={{
                      ...donePillStyle,
                      ...(hoveredBtn === doneKey ? {
                        background: '#34d399',
                        color: 'var(--bg-base)',
                        borderColor: '#34d399',
                        transform: 'scale(1.05)',
                        boxShadow: '0 0 8px rgba(52, 211, 153, 0.4)',
                      } : {}),
                    }}
                  >
                    ✓ Done
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleFailed(session.id); }}
                    onMouseEnter={() => setHoveredBtn(failKey)}
                    onMouseLeave={() => setHoveredBtn(null)}
                    style={{
                      ...failedPillStyle,
                      ...(hoveredBtn === failKey ? {
                        background: '#f87171',
                        color: 'var(--bg-base)',
                        borderColor: '#f87171',
                        transform: 'scale(1.05)',
                        boxShadow: '0 0 8px rgba(248, 113, 113, 0.4)',
                      } : {}),
                    }}
                  >
                    ✗ Failed
                  </button>
                </div>
              </div>
            );
          }}
        />
      </div>
    </div>
  );
}
