import { useState } from "react";
import "../App.css";

function Chat() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Ask me about your logs and I'll pull relevant snippets." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setError("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      const resp = await fetch("/api/rag/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Request failed");
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer || "No answer returned." },
        ...(data.sources
          ? [{ role: "meta", content: `Sources: ${data.sources.map((s) => s.id).join(", ") || "none"}` }]
          : []),
      ]);
    } catch (err) {
      console.error(err);
      setError(err.message || "Something went wrong");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "I hit an error fetching the answer." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-shell">
      <div className="chat-window">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-bubble ${msg.role}`}>
            <div className="chat-role">{msg.role}</div>
            <div>{msg.content}</div>
          </div>
        ))}
        {loading && <div className="chat-bubble assistant">Thinking...</div>}
      </div>

      <div className="chat-input-row">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your logs…"
          rows={3}
        />
        <button onClick={sendMessage} disabled={loading}>
          {loading ? "Sending..." : "Send"}
        </button>
      </div>
      {error && <div className="error-text">{error}</div>}
    </div>
  );
}

export default Chat;
