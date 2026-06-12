import React, { useState, useRef, useEffect } from 'react';
import client from '../api/client';

const styles = `
  /* === ChatPanel Scoped Styles === */

  @keyframes chatMessageSlideIn {
    from {
      opacity: 0;
      transform: translateY(12px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes chatDotPulse {
    0%, 80%, 100% {
      opacity: 0.25;
      transform: scale(0.8);
    }
    40% {
      opacity: 1;
      transform: scale(1);
    }
  }

  @keyframes chatInputGlow {
    0%, 100% {
      box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.15);
    }
    50% {
      box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.3);
    }
  }

  @keyframes chatSendHover {
    0% { transform: translateX(0); }
    50% { transform: translateX(2px); }
    100% { transform: translateX(0); }
  }

  .chat-panel {
    width: 380px;
    min-width: 380px;
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-surface);
    border-left: 1px solid var(--border-subtle);
    position: relative;
    font-family: var(--font-family);
  }

  /* Subtle gradient left border accent */
  .chat-panel::before {
    content: '';
    position: absolute;
    top: 0;
    left: -1px;
    width: 1px;
    height: 100%;
    background: linear-gradient(
      180deg,
      rgba(124, 92, 252, 0.0) 0%,
      rgba(124, 92, 252, 0.4) 30%,
      rgba(76, 201, 240, 0.3) 70%,
      rgba(76, 201, 240, 0.0) 100%
    );
    pointer-events: none;
    z-index: 1;
  }

  /* === Header === */
  .chat-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 20px;
    height: 56px;
    position: relative;
    flex-shrink: 0;
  }

  .chat-header::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 20px;
    right: 20px;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent 0%,
      var(--border-strong) 20%,
      var(--border-strong) 80%,
      transparent 100%
    );
  }

  .chat-header-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-md);
    background: var(--accent-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    box-shadow: 0 2px 12px rgba(124, 92, 252, 0.3);
    flex-shrink: 0;
  }

  .chat-header-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.01em;
  }

  .chat-header-status {
    font-size: var(--font-size-xs);
    color: var(--text-tertiary);
    font-weight: var(--font-weight-normal);
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .chat-header-status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 6px rgba(52, 211, 153, 0.5);
  }

  /* === Messages Area === */
  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    scroll-behavior: smooth;
  }

  .chat-messages::-webkit-scrollbar {
    width: 4px;
  }

  .chat-messages::-webkit-scrollbar-track {
    background: transparent;
  }

  .chat-messages::-webkit-scrollbar-thumb {
    background: var(--text-tertiary);
    border-radius: var(--radius-full);
  }

  /* === Message Bubbles === */
  .chat-message-row {
    display: flex;
    animation: chatMessageSlideIn 0.35s var(--transition-base) both;
  }

  .chat-message-row--user {
    justify-content: flex-end;
  }

  .chat-message-row--assistant {
    justify-content: flex-start;
  }

  .chat-bubble {
    max-width: 82%;
    padding: 10px 14px;
    font-size: var(--font-size-sm);
    line-height: 1.55;
    word-wrap: break-word;
    overflow-wrap: break-word;
  }

  .chat-bubble--user {
    background: var(--accent-gradient);
    color: #ffffff;
    border-radius: 16px 16px 4px 16px;
    box-shadow: 0 2px 12px rgba(124, 92, 252, 0.25);
  }

  .chat-bubble--assistant {
    background: rgba(22, 22, 42, 0.5);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: var(--text-primary);
    border-radius: 16px 16px 16px 4px;
  }

  /* === Loading Dots === */
  .chat-loading-row {
    display: flex;
    justify-content: flex-start;
    animation: chatMessageSlideIn 0.3s ease-out both;
  }

  .chat-loading-bubble {
    background: rgba(22, 22, 42, 0.5);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px 16px 16px 4px;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .chat-loading-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-secondary);
    animation: chatDotPulse 1.4s ease-in-out infinite;
  }

  .chat-loading-dot:nth-child(2) {
    animation-delay: 0.2s;
  }

  .chat-loading-dot:nth-child(3) {
    animation-delay: 0.4s;
  }

  /* === Input Area === */
  .chat-input-area {
    padding: 16px;
    flex-shrink: 0;
    position: relative;
  }

  .chat-input-area::before {
    content: '';
    position: absolute;
    top: 0;
    left: 16px;
    right: 16px;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent 0%,
      var(--border-strong) 20%,
      var(--border-strong) 80%,
      transparent 100%
    );
  }

  .chat-input-wrapper {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 4px 4px 4px 14px;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }

  .chat-input-wrapper:focus-within {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px var(--accent-primary-glow);
  }

  .chat-input {
    flex: 1;
    background: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    color: var(--text-primary);
    font-family: var(--font-family);
    font-size: var(--font-size-sm);
    padding: 8px 0 !important;
    width: 100%;
  }

  .chat-input::placeholder {
    color: var(--text-tertiary);
  }

  .chat-input:focus {
    box-shadow: none !important;
    border: none !important;
  }

  .chat-send-btn {
    width: 36px;
    height: 36px;
    min-width: 36px;
    border-radius: var(--radius-md);
    background: var(--accent-gradient);
    color: #ffffff;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 16px;
    font-weight: var(--font-weight-bold);
    transition: all var(--transition-fast);
    box-shadow: 0 2px 8px rgba(124, 92, 252, 0.3);
    padding: 0;
    flex-shrink: 0;
  }

  .chat-send-btn:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 4px 16px rgba(124, 92, 252, 0.4);
  }

  .chat-send-btn:active:not(:disabled) {
    transform: scale(0.95);
  }

  .chat-send-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  .chat-send-btn svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
`;

const renderMessageContent = (text) => {
  if (!text) return null;
  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    // Check for bullet point
    const bulletMatch = line.match(/^\s*[\*\-]\s+(.*)/);

    const parseInline = (content) => {
      // Split by bold patterns **bold** (non-greedy)
      const parts = content.split(/(\*\*[^*]+?\*\*)/g);
      return parts.map((part, partIdx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={partIdx}>{part.slice(2, -2)}</strong>;
        }
        // Split by single asterisk for italics: *italic* (non-greedy)
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
      const response = await client.post('/api/chat', {
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
    <>
      <style>{styles}</style>
      <div className="chat-panel">
        {/* Header */}
        <div className="chat-header">
          <div className="chat-header-icon" aria-hidden="true" style={{ color: '#fff', fontSize: '15px', fontWeight: 700 }}>T</div>
          <span className="chat-header-title">Tempo AI</span>
          <div className="chat-header-status">
            <span className="chat-header-status-dot" />
            Online
          </div>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`chat-message-row chat-message-row--${m.role}`}
              style={{ animationDelay: `${Math.min(i * 0.05, 0.3)}s` }}
            >
              <div className={`chat-bubble chat-bubble--${m.role}`}>
                {renderMessageContent(m.content)}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-loading-row">
              <div className="chat-loading-bubble">
                <div className="chat-loading-dot" />
                <div className="chat-loading-dot" />
                <div className="chat-loading-dot" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <input
              type="text"
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Message Tempo…"
              disabled={loading}
              autoComplete="off"
            />
            <button
              className="chat-send-btn"
              onClick={handleSend}
              disabled={loading || !input.trim()}
              aria-label="Send message"
            >
              <svg viewBox="0 0 24 24">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
