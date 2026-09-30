import React, { useState, useEffect } from 'react';
import {
  GitBranch,
  Search,
  Filter,
  Layers,
  Sparkles,
  Maximize2,
  RefreshCw,
  X,
  FileText,
  Tag,
  Share2,
} from 'lucide-react';
import GraphCanvas from './GraphCanvas';

export default function FullGraphExplorer({ fullGraphData, setFullGraphData }) {
  const [keyword, setKeyword] = useState('');
  const [limit, setLimit] = useState(75);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);

  useEffect(() => {
    fetchGraphData(keyword, limit);
  }, [limit]);

  const fetchGraphData = async (kw = '', lim = 75) => {
    setLoading(true);
    try {
      const url = kw
        ? `/api/graph/explore?keyword=${encodeURIComponent(kw)}&limit=${lim}`
        : `/api/graph/explore?limit=${lim}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setFullGraphData(data);
      }
    } catch (e) {
      console.error('Error exploring graph:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchGraphData(keyword, limit);
  };

  const handleNodeSelect = (node) => {
    setSelectedNode(node);
  };

  // Find connected links for selected node
  const connectedLinks = selectedNode && fullGraphData?.links
    ? fullGraphData.links.filter(
        (l) => l.source === selectedNode.id || l.target === selectedNode.id ||
              l.source?.id === selectedNode.id || l.target?.id === selectedNode.id
      )
    : [];

  return (
    <div>
      {/* Top Filter Bar */}
      <div className="brutal-panel">
        <div className="brutal-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <GitBranch size={16} color="var(--accent-indigo)" />
            <span style={{ color: 'var(--accent-indigo)' }}>Full-Page Knowledge Graph Explorer</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span className="badge-brutal cyan">{fullGraphData?.nodes?.length || 0} Nodes</span>
            <span className="badge-brutal green">{fullGraphData?.links?.length || 0} Relationships</span>
          </div>
        </div>

        <div className="brutal-panel-body">
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <div className="prompt-bar-input" style={{ flex: 1, minWidth: '260px' }}>
              <div className="prompt-symbol"><Search size={16} /></div>
              <input
                type="text"
                className="prompt-field"
                placeholder="Search entity name or concept (e.g., 'Transformer', 'Hallucination', 'RAG')..."
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Max Edges:</span>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                style={{
                  background: 'rgba(10, 15, 33, 0.95)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-glass)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.65rem 0.85rem',
                  fontFamily: 'var(--font-sans)',
                  fontSize: '0.825rem',
                  fontWeight: 600,
                  outline: 'none',
                  cursor: 'pointer',
                }}
              >
                <option value={25}>25 Edges</option>
                <option value={50}>50 Edges</option>
                <option value={75}>75 Edges</option>
                <option value={100}>100 Edges</option>
                <option value={150}>150 Edges</option>
                <option value={200}>200 Edges</option>
              </select>
            </div>

            <button type="submit" className="btn-brutal" disabled={loading}>
              Query Graph
            </button>

            {keyword && (
              <button
                type="button"
                className="btn-brutal-secondary"
                onClick={() => {
                  setKeyword('');
                  fetchGraphData('', limit);
                }}
              >
                Reset
              </button>
            )}
          </form>
        </div>
      </div>

      {/* Canvas & Node Inspector Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: selectedNode ? 'minmax(0, 1fr) 340px' : 'minmax(0, 1fr)',
          gap: '1.5rem',
          height: 'calc(100vh - 260px)',
          minHeight: '620px',
        }}
      >
        <div style={{ height: '100%', width: '100%', minHeight: 0 }}>
          <GraphCanvas graphData={fullGraphData} onNodeSelect={handleNodeSelect} />
        </div>

        {/* Node Inspector Sidebar */}
        {selectedNode && (
          <div className="brutal-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', margin: 0, overflow: 'hidden' }}>
            <div className="brutal-panel-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Tag size={15} color="var(--neon-cyan)" />
                <span>Node Inspector</span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            <div className="brutal-panel-body" style={{ overflowY: 'auto', flex: 1 }}>
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', wordBreak: 'break-word' }}>
                  {selectedNode.label || selectedNode.id}
                </div>
                <div style={{ marginTop: '0.4rem', display: 'flex', gap: '0.4rem' }}>
                  <span className="badge-brutal cyan">{selectedNode.type || 'Entity'}</span>
                  <span className="badge-brutal green">{connectedLinks.length} Connections</span>
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.85rem', marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '0.5rem' }}>
                  CONNECTED RELATIONSHIPS:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {connectedLinks.length === 0 ? (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No local relationships rendered</div>
                  ) : (
                    connectedLinks.map((l, idx) => {
                      const sId = typeof l.source === 'object' ? l.source?.id : l.source;
                      const tId = typeof l.target === 'object' ? l.target?.id : l.target;
                      const sLabel = typeof l.source === 'object' ? l.source?.label || sId : sId;
                      const tLabel = typeof l.target === 'object' ? l.target?.label || tId : tId;
                      const isOutgoing = sId === selectedNode.id;

                      return (
                        <div key={idx} className="traversal-step" style={{ flexDirection: 'column', gap: '0.25rem', padding: '0.65rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.775rem', fontWeight: 600 }}>
                            <span style={{ color: isOutgoing ? 'var(--neon-indigo)' : 'var(--neon-amber)' }}>
                              {isOutgoing ? 'Outgoing ──>' : '<── Incoming'}
                            </span>
                            <span className="badge-brutal purple" style={{ fontSize: '0.65rem' }}>{l.relation}</span>
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                            {isOutgoing ? `To: ${tLabel}` : `From: ${sLabel}`}
                          </div>
                          {l.paper_id && (
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                              Source Paper: {l.paper_id}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              <button
                className="btn-brutal"
                style={{ width: '100%', fontSize: '0.8rem', padding: '0.6rem' }}
                onClick={() => {
                  setKeyword(selectedNode.label || selectedNode.id);
                  fetchGraphData(selectedNode.label || selectedNode.id, limit);
                }}
              >
                Center Graph on This Node
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
