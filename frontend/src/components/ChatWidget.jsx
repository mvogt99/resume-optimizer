import React, { useState, useRef, useEffect } from "react";

export default function ChatWidget({ userId }) {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [ticketForm, setTicketForm] = useState({ title: "", description: "", ticket_type: "bug" });
  const [loading, setLoading] = useState(false);
  const [ticketSent, setTicketSent] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const sendMessage = async () => {
    const message = inputText.trim();
    if (!message || loading) return;
    const userMsg = { role: "user", content: message };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInputText("");
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/chat/message", {
        method: "POST",
        headers: { "Content-Type": "application/json", "user-id": String(userId) },
        body: JSON.stringify({ message, history: messages }),
      });
      if (!response.ok) throw new Error("non-ok");
      const data = await response.json();
      setMessages([...nextMessages, { role: "assistant", content: data.response }]);
    } catch {
      setError("Failed to get response. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const submitTicket = async () => {
    const { title, description } = ticketForm;
    if (title.length < 5) { setError("Title must be at least 5 characters."); return; }
    if (description.length < 10) { setError("Description must be at least 10 characters."); return; }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/chat/ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json", "user-id": String(userId) },
        body: JSON.stringify(ticketForm),
      });
      if (!response.ok) throw new Error("non-ok");
      const data = await response.json();
      if (data.status === "created") {
        setTicketSent(true);
      } else {
        setError("Gateway unavailable. Your report has been noted.");
      }
    } catch {
      setError("Failed to submit. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setIsOpen(false);
    setMode(null);
    setMessages([]);
    setInputText("");
    setTicketForm({ title: "", description: "", ticket_type: "bug" });
    setLoading(false);
    setTicketSent(false);
    setError(null);
  };

  const bubbleStyle = {
    position: "fixed", bottom: "24px", right: "90px", zIndex: 9999,
    width: "56px", height: "56px", borderRadius: "50%",
    backgroundColor: "#2563eb", color: "white", fontSize: "24px",
    display: "flex", alignItems: "center", justifyContent: "center",
    cursor: "pointer", border: "none",
  };

  const btnPrimary = {
    width: "100%", padding: "12px", marginBottom: "8px",
    backgroundColor: "#2563eb", color: "white", borderRadius: "8px",
    border: "none", cursor: "pointer",
  };

  const msgBase = { maxWidth: "80%", marginBottom: "8px", padding: "8px 12px" };

  return (
    <>
      {isOpen && (
        <div style={{
          position: "fixed", bottom: "90px", right: "90px", zIndex: 9999,
          width: "360px", height: "480px", backgroundColor: "white",
          borderRadius: "12px", boxShadow: "0 4px 24px rgba(0,0,0,0.18)",
          display: "flex", flexDirection: "column",
        }}>
          {/* Header */}
          <div style={{
            padding: "16px", backgroundColor: "#2563eb", color: "white",
            borderRadius: "12px 12px 0 0", display: "flex",
            justifyContent: "space-between", alignItems: "center",
          }}>
            <h3 style={{ margin: 0, fontSize: "16px" }}>Resume Assistant</h3>
            <button onClick={reset} style={{
              background: "transparent", border: "none", color: "white",
              fontSize: "20px", cursor: "pointer", lineHeight: 1,
            }}>×</button>
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
            {mode === null && (
              <>
                <p style={{ textAlign: "center", marginBottom: "16px" }}>How can I help you?</p>
                <button style={btnPrimary} onClick={() => setMode("qa")}>Ask about my resume</button>
                <button style={btnPrimary} onClick={() => setMode("ticket")}>Report an issue</button>
              </>
            )}

            {mode === "qa" && (
              <>
                {messages.length === 0 && !loading && (
                  <p style={{ color: "#64748b", fontSize: "14px" }}>
                    Ask me anything about your resume, ATS score, or job match.
                  </p>
                )}
                {messages.map((msg, i) => (
                  <div key={i} style={{
                    ...msgBase,
                    borderRadius: msg.role === "user" ? "12px 12px 0 12px" : "12px 12px 12px 0",
                    backgroundColor: msg.role === "user" ? "#2563eb" : "#f1f5f9",
                    color: msg.role === "user" ? "white" : "#1e293b",
                    marginLeft: msg.role === "user" ? "auto" : 0,
                  }}>{msg.content}</div>
                ))}
                {loading && (
                  <div style={{ ...msgBase, borderRadius: "12px 12px 12px 0", backgroundColor: "#f1f5f9", color: "#64748b" }}>
                    Thinking...
                  </div>
                )}
                {error && <p style={{ color: "red", fontSize: "13px" }}>{error}</p>}
                <div ref={messagesEndRef} />
              </>
            )}

            {mode === "ticket" && (
              ticketSent ? (
                <p style={{ textAlign: "center", color: "#16a34a", marginTop: "40px" }}>
                  ✓ Ticket submitted — the team will review it.
                </p>
              ) : (
                <>
                  <div style={{ marginBottom: "12px" }}>
                    <label style={{ marginRight: "16px", cursor: "pointer" }}>
                      <input type="radio" value="bug" checked={ticketForm.ticket_type === "bug"}
                        onChange={() => setTicketForm({ ...ticketForm, ticket_type: "bug" })} /> Bug Report
                    </label>
                    <label style={{ cursor: "pointer" }}>
                      <input type="radio" value="feature" checked={ticketForm.ticket_type === "feature"}
                        onChange={() => setTicketForm({ ...ticketForm, ticket_type: "feature" })} /> Feature Request
                    </label>
                  </div>
                  <input type="text" placeholder="Brief summary..." value={ticketForm.title}
                    onChange={(e) => setTicketForm({ ...ticketForm, title: e.target.value })}
                    style={{ width: "100%", padding: "8px", marginBottom: "8px", border: "1px solid #e2e8f0", borderRadius: "8px", boxSizing: "border-box" }} />
                  <textarea placeholder="Describe the issue or feature..." value={ticketForm.description}
                    onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })} rows={4}
                    style={{ width: "100%", padding: "8px", marginBottom: "8px", border: "1px solid #e2e8f0", borderRadius: "8px", boxSizing: "border-box", resize: "vertical" }} />
                  <button onClick={submitTicket} disabled={loading} style={{ ...btnPrimary, opacity: loading ? 0.6 : 1, cursor: loading ? "not-allowed" : "pointer" }}>
                    Submit
                  </button>
                  {error && <p style={{ color: "red", fontSize: "13px" }}>{error}</p>}
                </>
              )
            )}
          </div>

          {/* Footer — Q&A input */}
          {mode === "qa" && (
            <div style={{ display: "flex", padding: "12px 16px", borderTop: "1px solid #e2e8f0", gap: "8px" }}>
              <input type="text" placeholder="Type a message..." value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                disabled={loading}
                style={{ flex: 1, padding: "8px", border: "1px solid #e2e8f0", borderRadius: "8px" }} />
              <button onClick={sendMessage} disabled={loading}
                style={{ padding: "8px 16px", backgroundColor: "#2563eb", color: "white", borderRadius: "8px", border: "none", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1 }}>
                Send
              </button>
            </div>
          )}
        </div>
      )}

      {/* Bubble — always visible */}
      <button style={bubbleStyle} onClick={() => setIsOpen(!isOpen)}>💬</button>
    </>
  );
}
