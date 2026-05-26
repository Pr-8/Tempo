import React, { useState } from 'react';
import client from '../api/client';

export default function AddTaskForm({ onTaskAdded }) {
  const [type, setType] = useState('task'); // 'task' or 'event'
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
      const payload = {
        title: formData.title,
        course: formData.course,
        priority: formData.priority,
        is_fixed: type === 'event',
      };

      if (type === 'event') {
        payload.fixed_start = formData.fixed_start;
        payload.fixed_end = formData.fixed_end;
      } else {
        payload.estimated_hours = parseFloat(formData.estimated_hours);
        payload.deadline = formData.deadline;
        // Optional draft time for tasks
        if (formData.fixed_start && formData.fixed_end) {
          payload.fixed_start = formData.fixed_start;
          payload.fixed_end = formData.fixed_end;
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
      if (onTaskAdded) onTaskAdded();
    } catch (err) {
      alert('Error adding: ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '15px', border: '1px solid #e5e7eb', borderRadius: '8px', backgroundColor: 'white' }}>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '5px' }}>
        <button 
          type="button" 
          onClick={() => setType('task')}
          style={{ flex: 1, padding: '8px', borderRadius: '6px', border: '1px solid #3b82f6', backgroundColor: type === 'task' ? '#3b82f6' : 'white', color: type === 'task' ? 'white' : '#3b82f6', cursor: 'pointer', fontWeight: 'bold' }}
        >
          Add Task
        </button>
        <button 
          type="button" 
          onClick={() => setType('event')}
          style={{ flex: 1, padding: '8px', borderRadius: '6px', border: '1px solid #ef4444', backgroundColor: type === 'event' ? '#ef4444' : 'white', color: type === 'event' ? 'white' : '#ef4444', cursor: 'pointer', fontWeight: 'bold' }}
        >
          Add Event
        </button>
      </div>

      <input
        placeholder="Title (e.g. Calculus Prep)"
        value={formData.title}
        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
        required
        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
      />
      <input
        placeholder="Course (Optional)"
        value={formData.course}
        onChange={(e) => setFormData({ ...formData, course: e.target.value })}
        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
      />

      {type === 'task' ? (
        <>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="number"
              step="0.5"
              placeholder="Hours"
              value={formData.estimated_hours}
              onChange={(e) => setFormData({ ...formData, estimated_hours: e.target.value })}
              required
              style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
            />
            <input
              type="date"
              value={formData.deadline}
              onChange={(e) => setFormData({ ...formData, deadline: e.target.value })}
              required
              style={{ flex: 2, padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
            />
          </div>
          <div style={{ fontSize: '11px', color: '#6b7280', marginTop: '5px' }}>
            Optional: Set a draft time (AI can move this later)
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="datetime-local"
              value={formData.fixed_start}
              onChange={(e) => setFormData({ ...formData, fixed_start: e.target.value })}
              style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db', fontSize: '11px' }}
            />
            <input
              type="datetime-local"
              value={formData.fixed_end}
              onChange={(e) => setFormData({ ...formData, fixed_end: e.target.value })}
              style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db', fontSize: '11px' }}
            />
          </div>
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <label style={{ fontSize: '12px', fontWeight: 'bold' }}>Fixed Time Range:</label>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="datetime-local"
              value={formData.fixed_start}
              onChange={(e) => setFormData({ ...formData, fixed_start: e.target.value })}
              required
              style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
            />
            <input
              type="datetime-local"
              value={formData.fixed_end}
              onChange={(e) => setFormData({ ...formData, fixed_end: e.target.value })}
              required
              style={{ flex: 1, padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
            />
          </div>
        </div>
      )}

      <select
        value={formData.priority}
        onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
      >
        <option value="low">Low Priority</option>
        <option value="medium">Medium Priority</option>
        <option value="high">High Priority</option>
      </select>

      <button 
        type="submit"
        style={{ padding: '10px', borderRadius: '6px', border: 'none', backgroundColor: '#111827', color: 'white', fontWeight: 'bold', cursor: 'pointer', marginTop: '5px' }}
      >
        Save {type === 'task' ? 'Task' : 'Event'}
      </button>
    </form>
  );
}
