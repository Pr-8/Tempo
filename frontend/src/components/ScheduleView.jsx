import React, { useState, useEffect } from 'react';
import FullCalendar from '@fullcalendar/react';
import timeGridPlugin from '@fullcalendar/timegrid';
import client from '../api/client';

export default function ScheduleView() {
  const [sessions, setSessions] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [prefs, setPrefs] = useState(null);

  const fetchData = async () => {
    try {
      const [sessionsRes, tasksRes, prefsRes] = await Promise.all([
        client.get('/api/sessions/'),
        client.get('/api/tasks/'),
        client.get('/api/preferences/')
      ]);
      setSessions(sessionsRes.data);
      setTasks(tasksRes.data);
      setPrefs(prefsRes.data);
    } catch (err) {
      console.error('Error fetching data:', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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
      setTimeout(fetchData, 2000); // Wait for reschedule
    } catch (err) {
      alert('Error marking session failed');
    }
  };

  const taskMap = Object.fromEntries(tasks.map(t => [t.id, t]));
  const events = sessions.map(s => {
    const task = taskMap[s.task_id];
    return {
      id: s.id,
      title: task?.title || 'Unknown Task',
      start: s.start_time,
      end: s.end_time,
      extendedProps: { session: s, task: task }
    };
  });

  const priorityColors = { high: '#ef4444', medium: '#f59e0b', low: '#10b981' };

  return (
    <div style={{ flex: 1, padding: '20px' }}>
      {prefs?.last_schedule_explanation && (
        <div style={{ backgroundColor: '#f3f4f6', padding: '15px', borderRadius: '8px', marginBottom: '20px', borderLeft: '4px solid #3b82f6' }}>
          <strong>Coach says:</strong>
          <p style={{ margin: '5px 0 0 0', fontSize: '14px' }}>{prefs.last_schedule_explanation}</p>
        </div>
      )}
      <FullCalendar
        plugins={[timeGridPlugin]}
        initialView="timeGridWeek"
        events={events}
        headerToolbar={{
          left: 'prev,next today',
          center: 'title',
          right: ''
        }}
        slotMinTime="07:00:00"
        slotMaxTime="22:00:00"
        allDaySlot={false}
        height="auto"
        eventContent={(eventInfo) => {
          const { task, session } = eventInfo.event.extendedProps;
          return (
            <div style={{ fontSize: '11px', overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: priorityColors[task?.priority] || '#ccc' }}></span>
                <strong>{eventInfo.event.title}</strong>
              </div>
              {task?.course && <div style={{ opacity: 0.8 }}>{task.course}</div>}
              <div style={{ marginTop: '4px', display: 'flex', gap: '4px' }}>
                <button onClick={() => handleComplete(session.id)} style={{ fontSize: '9px', padding: '2px 4px' }}>✓ Done</button>
                <button onClick={() => handleFailed(session.id)} style={{ fontSize: '9px', padding: '2px 4px' }}>✗ Failed</button>
              </div>
            </div>
          );
        }}
      />
    </div>
  );
}
