import React, { useState, useEffect } from 'react';
import AddTaskForm from './components/AddTaskForm';
import ScheduleView from './components/ScheduleView';
import client from './api/client';

function App() {
  const [tasks, setTasks] = useState([]);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const fetchTasks = async () => {
    try {
      const res = await client.get('/api/tasks/');
      setTasks(res.data);
    } catch (err) {
      console.error('Error fetching tasks:', err);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [refreshTrigger]);

  const handleTaskAdded = () => {
    setRefreshTrigger(prev => prev + 1);
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

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
      <div style={{ width: '350px', borderRight: '1px solid #eee', padding: '20px', overflowY: 'auto' }}>
        <h1>Tempo</h1>
        <AddTaskForm onTaskAdded={handleTaskAdded} />
        
        <div style={{ marginTop: '30px' }}>
          <h3>All Tasks</h3>
          {tasks.map(task => (
            <div key={task.id} style={{ padding: '10px', borderBottom: '1px solid #f0f0f0', position: 'relative' }}>
              <div style={{ fontWeight: 'bold' }}>{task.title}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>Due: {task.deadline}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>Priority: {task.priority} | Status: {task.status}</div>
              <button 
                onClick={() => handleDeleteTask(task.id)}
                style={{ position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', cursor: 'pointer', color: 'red' }}
              >
                🗑️
              </button>
            </div>
          ))}
        </div>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', backgroundColor: '#fafafa' }}>
        <ScheduleView key={refreshTrigger} />
      </div>
    </div>
  );
}

export default App;
