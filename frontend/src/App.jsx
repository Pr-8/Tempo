import React, { useState, useEffect } from 'react';
import AddTaskForm from './components/AddTaskForm';
import ScheduleView from './components/ScheduleView';
import ChatPanel from './components/ChatPanel';
import client from './api/client';

function App() {
  const [tasks, setTasks] = useState([]);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // WebSocket for Real-time updates
  useEffect(() => {
    const connectWS = () => {
      const ws = new WebSocket('ws://localhost:8000/ws');
      
      ws.onmessage = (event) => {
        if (event.data === 'REFRESH') {
          console.log('Real-time refresh triggered');
          setRefreshTrigger(prev => prev + 1);
        }
      };

      ws.onclose = () => {
        console.log('WS closed, reconnecting in 3s...');
        setTimeout(connectWS, 3000);
      };

      return ws;
    };

    const socket = connectWS();
    return () => {
      socket.onclose = null; // Prevent reconnect on unmount
      socket.close();
    };
  }, []);

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
    fetchTasks();
    setRefreshTrigger(prev => prev + 1);
  };

  const handleReschedule = async () => {
    try {
      await client.post('/api/sessions/reschedule');
      setRefreshTrigger(prev => prev + 1);
      alert('Reschedule complete!');
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
        <div style={{ padding: '20px', display: 'flex', justifyContent: 'flex-end' }}>
          <button 
            onClick={handleReschedule}
            style={{ padding: '10px 20px', backgroundColor: '#111827', color: 'white', borderRadius: '6px', cursor: 'pointer', border: 'none', fontWeight: 'bold' }}
          >
            🚀 Schedule (Nuke)
          </button>
        </div>
        <ScheduleView key={refreshTrigger} />
      </div>
      <ChatPanel />
    </div>
  );
}

export default App;
