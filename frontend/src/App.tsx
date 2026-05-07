import { ChatUI } from "./components/ChatUI";

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>agent-sample</h1>
        <span className="app-subtitle">LangGraph + Ollama (gemma4)</span>
      </header>
      <ChatUI />
    </div>
  );
}
