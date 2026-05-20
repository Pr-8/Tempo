import React, { useState } from 'react';
import client from '../api/client';

export default function AddTaskForm({ onTaskAdded }) {
  const [formData, setFormData] = useState({
    title: '',
    course: '',
    estimated_hours: '',
    deadline: '',
    priority: 'medium'
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await client.post('/api/tasks/', {
        ...formData,
        estimated_hours: parseFloat(formData.estimated_hours)
      });
      setFormData({
        title: '',
        course: '',
        estimated_hours: '',
        deadline: '',
        priority: 'medium'
      });
      if (onTaskAdded) onTaskAdded();
    } catch (err) {
      alert('Error adding task: ' + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '20px', border: '1px solid #ccc', borderRadius: '8px' }}>
      <h3>Add New Task</h3>
      <input
        placeholder="Title"
        value={formData.title}
        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
        required
      />
      <input
        placeholder="Course (Optional)"
        value={formData.course}
        onChange={(e) => setFormData({ ...formData, course: e.target.value })}
      />
      <input
        type="number"
        step="0.5"
        placeholder="Estimated Hours"
        value={formData.estimated_hours}
        onChange={(e) => setFormData({ ...formData, estimated_hours: e.target.value })}
        required
      />
      <input
        type="date"
        value={formData.deadline}
        onChange={(e) => setFormData({ ...formData, deadline: e.target.value })}
        required
      />
      <select
        value={formData.priority}
        onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
      >
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
      <button type="submit">Add Task</button>
    </form>
  );
}
