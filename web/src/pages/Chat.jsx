import { useState } from 'react'
import { Link } from 'react-router-dom'
import './Chat.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      const data = await res.json()
        setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response,
          source: data.source,
          redacted: data.redacted,
          confidence: data.confidence,
          tool_calls: data.tool_calls || null,
          encrypted_entities: data.encrypted_entities || null,
          encrypted_message: data.encrypted_message || null,
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${err.message}`,
          error: true,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-page">
      <header className="chat-header">
        <Link to="/" className="back-link">cloudNein</Link>
        <h1 className="chat-title">Chat</h1>
      </header>
      <div className="chat-main">
        <div className="messages">
          {messages.length === 0 && (
            <p className="messages-empty">
              Send a message. Sensitive names and data are processed locally
              and not sent to the cloud.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`message message--${m.role} ${m.error ? 'message--error' : ''}`}
            >
              {m.tool_calls && m.tool_calls.length > 0 && (
                <div className="message-tools">
                  <span className="message-tools-label">Tool used</span>
                  {m.tool_calls.map((tc, j) => (
                    <div key={j} className="message-tool-call">
                      <span className="message-tool-name">
                        {tc.name.replace(/_/g, ' ')}
                      </span>
                      <dl className="message-tool-args">
                        {Object.entries(tc.arguments || {}).map(([k, v]) => (
                          <div key={k} className="message-tool-arg">
                            <dt>{k}</dt>
                            <dd>{v}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  ))}
                  {m.encrypted_message && (
                    <dl className="message-tool-args">
                      <div className="message-tool-arg">
                        <dt>Sent to server</dt>
                        <dd className="message-tool-encrypted">
                          {m.encrypted_message}
                        </dd>
                      </div>
                    </dl>
                  )}
                  {m.encrypted_entities?.length > 0 && (
                    <dl className="message-tool-args">
                      {m.encrypted_entities.map((ee, i) => (
                        <div key={i} className="message-tool-arg">
                          <dt>{ee.label} → encrypted</dt>
                          <dd className="message-tool-encrypted">{ee.encrypted}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </div>
              )}
              <div className="message-content">{m.content}</div>
              {(m.source || m.confidence != null) && (
                <div className="message-meta">
                  <span className="message-badge">
                    {m.redacted
                      ? 'Processed locally, answered via cloud'
                      : m.source}
                  </span>
                  {m.confidence != null && (
                    <span className="message-confidence">
                      {(m.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="message message--assistant">
              <div className="message-content">...</div>
            </div>
          )}
        </div>
        <form className="chat-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            disabled={loading}
            className="chat-input"
            autoFocus
          />
          <button type="submit" disabled={loading} className="chat-send">
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
