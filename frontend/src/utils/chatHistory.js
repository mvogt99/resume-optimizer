/**
 * Chat history save utilities.
 *
 * saveChatHistoryFromServer(api, sessionType, sessionId)
 *   — fetches history from backend and triggers a .txt download
 *
 * saveChatHistoryFromMessages(messages, label)
 *   — formats an in-memory messages array and triggers a .txt download
 *   — used for stateless sessions (e.g. Expert Comparison) where history
 *     is only in React state
 */

function _formatTranscript(label, messages) {
  const now = new Date().toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
  const lines = [
    `Chat History — ${label}`,
    `Exported: ${now}`,
    '='.repeat(60),
    '',
  ];
  for (const msg of messages) {
    const roleLabel = msg.role === 'user' ? 'You' : 'AI';
    const ts = msg.created_at ? `  ${String(msg.created_at).slice(0, 19)}` : '';
    lines.push(`[${roleLabel}]${ts}`);
    lines.push(msg.content || '');
    lines.push('');
  }
  return lines.join('\n');
}

function _triggerDownload(text, filename) {
  const blob = new Blob([text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export async function saveChatHistoryFromServer(api, sessionType, sessionId) {
  const data = await api.getChatHistory(sessionType, sessionId);
  const label = data.label || sessionType;
  const text = _formatTranscript(label, data.messages || []);
  _triggerDownload(text, `chat_history_${sessionType}_${sessionId}.txt`);
}

export function saveChatHistoryFromMessages(messages, label) {
  const text = _formatTranscript(label, messages);
  const slug = label.toLowerCase().replace(/\s+/g, '_');
  _triggerDownload(text, `chat_history_${slug}.txt`);
}
