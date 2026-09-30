import React, { useState, useEffect } from 'react';
import {
  Clock,
  FileText,
  Copy,
  Check,
  Trash2,
  Download,
  Terminal,
  ArrowRight,
  GitBranch,
  Sparkles,
} from 'lucide-react';

export default function AnswerHistory({ onSelectQuery }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data || []);
      }
    } catch (e) {
      console.error('Error fetching history:', e);
    } finally {
      setLoading(false);
    }
  };

  const copyAnswer = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const exportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(history, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `graphrag_query_history_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const clearHistory = async () => {
    if (!window.confirm('Clear all stored query execution history?')) return;
    try {
      setHistory([]);
    } catch (e) {
      console.error('Error clearing history:', e);
    }
  };

  return (
    <div>
      {/* Top Header & Export Controls */}
      <div className="brutal-panel">
        <div className="brutal-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Clock size={16} color="var(--accent-indigo)" />
            <span style={{ color: 'var(--accent-indigo)' }}>GraphRAG Answer History</span>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="btn-brutal-secondary"
              style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem' }}
              disabled={history.length === 0}
              onClick={exportJSON}
            >
              <Download size={13} /> Export JSON
            </button>
            <button
              className="btn-brutal-danger"
              style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem' }}
              disabled={history.length === 0}
              onClick={clearHistory}
            >
              <Trash2 size={13} /> Clear
            </button>
          </div>
        </div>

        <div className="brutal-panel-body">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Total Executed Queries: <strong style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{history.length}</strong>
            </div>
            <div style={{ fontSize: '0.775rem', color: 'var(--text-muted)' }}>
              Automatically synced across your research sessions
            </div>
          </div>
        </div>
      </div>

      {/* Query History Items List */}
      {history.length === 0 ? (
        <div className="brutal-panel">
          <div className="brutal-panel-body" style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--text-muted)' }}>
            <Sparkles size={32} color="var(--accent-indigo)" style={{ marginBottom: '0.75rem', opacity: 0.5 }} />
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              No query history recorded yet
            </div>
            <div style={{ fontSize: '0.8rem', marginTop: '0.4rem' }}>
              Queries asked in the Dashboard will appear here with full execution traces and citations.
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {history.map((item, idx) => (
            <div key={idx} className="brutal-panel" style={{ margin: 0 }}>
              <div className="brutal-panel-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ color: 'var(--accent-indigo)', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>#{history.length - idx}</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>"{item.question}"</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {item.latency_sec && (
                    <span className="badge-brutal cyan">
                      <Clock size={11} /> {item.latency_sec}s
                    </span>
                  )}
                  {item.timestamp && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              </div>

              <div className="brutal-panel-body">
                <div className="answer-lead" style={{ marginBottom: '1rem' }}>
                  {item.answer}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {item.cited_papers?.map((pId) => (
                      <span key={pId} className="badge-brutal purple">
                        <FileText size={11} /> Paper {pId}
                      </span>
                    ))}
                    {item.reasoning_path && (
                      <span className="badge-brutal green">
                        <GitBranch size={11} /> {item.reasoning_path.length} Hops
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button
                      className="btn-brutal-secondary"
                      style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                      onClick={() => copyAnswer(item.answer, idx)}
                    >
                      {copiedIdx === idx ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                      {copiedIdx === idx ? 'Copied' : 'Copy'}
                    </button>
                    <button
                      className="btn-brutal"
                      style={{ padding: '0.35rem 0.85rem', fontSize: '0.75rem' }}
                      onClick={() => onSelectQuery(item)}
                    >
                      Load into Prompt <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
