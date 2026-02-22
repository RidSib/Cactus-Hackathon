import { Link } from 'react-router-dom'
import './Landing.css'

export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-header">
        <span className="logo">cloudNein</span>
        <nav>
          <Link to="/chat" className="nav-link">Chat</Link>
        </nav>
      </header>
      <main className="landing-hero">
        <h1 className="tagline">Keeping what matters local.</h1>
        <p className="lead">
          Communicate with AI over the cloud without revealing sensitive data.
          Company names, people, and confidential details stay on your side—
          only safe, redacted context goes to the cloud.
        </p>
        <Link to="/chat" className="cta">Go to Chat</Link>
      </main>
      <footer className="landing-footer">
        Privacy-first LLM chat. Sensitive data never leaves your device.
      </footer>
    </div>
  )
}
