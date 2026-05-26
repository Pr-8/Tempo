import React, { useState, useRef, useEffect } from 'react';
import client from '../api/client';

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hi! I'm tempo. I can help you manage your study schedule. Try saying something like 'Add a 2 hour math task for tomorrow' or 'What do I have scheduled this week?'" }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await client.post('/api/chat/', {
        message: userMessage,
        history: messages.slice(-10) // Send last 10 messages for context
      });

      setMessages(prev => [...prev, { role: 'assistant', content: response.data.reply }]);
    } catch (err) {
      console.error('Chat error:', err);
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I'm having some trouble connecting. Please try again in a moment." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      width: '350px',
      borderLeft: '1px solid #e5e7eb',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: 'white'
    }}>
      <div style={{ padding: '15px', borderBottom: '1px solid #e5e7eb', fontWeight: 'bold' }}>
        Chat with tempo
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '15px' }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            marginBottom: '15px',
            textAlign: m.role === 'user' ? 'right' : 'left'
          }}>
            <div style={{
              display: 'inline-block',
              padding: '10px',
              borderRadius: '8px',
              maxWidth: '85%',
              backgroundColor: m.role === 'user' ? '#3b82f6' : '#f3f4f6',
              color: m.role === 'user' ? 'white' : 'black',
              fontSize: '14px',
              lineHeight: '1.4'
            }}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ textAlign: 'left', marginBottom: '15px' }}>
            <div style={{
              display: 'inline-block',
              padding: '10px',
              borderRadius: '8px',
              backgroundColor: '#f3f4f6',
              fontSize: '14px',
              color: '#6b7280'
            }}>
              tempo is thinking...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: '15px', borderTop: '1px solid #e5e7eb', display: 'flex', gap: '8px' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type a message..."
          style={{
            flex: 1,
            padding: '8px 12px',
            borderRadius: '6px',
            border: '1px solid #d1d5db',
            fontSize: '14px'
          }}
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            padding: '8px 15px',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '14px',
            opacity: (loading || !input.trim()) ? 0.5 : 1
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
