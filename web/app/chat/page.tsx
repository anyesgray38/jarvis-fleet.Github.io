import Link from 'next/link'
import AegisChat from '../components/AegisChat'

export default function ChatPage() {
  return <main className="main">
    <header className="top">
      <div><div className="eyebrow">AEGIS</div><h1>Talk to AEGIS</h1><p className="muted">Your private assistant, using your own model.</p></div>
      <Link href="/">Control center</Link>
    </header>
    <AegisChat title="Your conversation" subtitle="Ask questions, work through ideas, and review your study material." />
  </main>
}
