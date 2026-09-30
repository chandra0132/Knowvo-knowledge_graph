import React, { useState } from 'react';
import {
  Search,
  Clock,
  FileText,
  GitBranch,
  Layers,
  Sparkles,
  ExternalLink,
  Copy,
  Check,
  Maximize2,
  Activity,
  CheckCircle,
} from 'lucide-react';
import GraphCanvas from './GraphCanvas';
import TiltCard from './TiltCard';

const SAMPLE_QUESTIONS = [
  "How do recent methods mitigate LLM hallucination in QA or RAG tasks?",
  "Which models build on or extend the Transformer architecture?",
  "What datasets or benchmarks are used to evaluate factuality and hallucination?",
  "How does DexterSQL improve baseline retrieval/Text-to-SQL performance?",
  "What are the main causes or categories of hallucinations identified in the corpus?",
];

export default function DashboardQA({
  question,
  setQuestion,
  queryResult,
  loading,
  error,
  graphData,
  fullGraphData,
  setGraphData,
  handleQuery,
  onOpenFullGraph,
}) {
  const [activeTab, setActiveTab] = useState('reasoning'); // 'reasoning' | 'evidence'
  const [copied, setCopied] = useState(false);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      {/* Top Prompt Console */}
      <TiltCard maxTilt={5} scale={1.005} style={{ marginBottom: '1.5rem' }}>
        <div className="brutal-panel" style={{ margin: 0 }}>
          <div className="brutal-panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sparkles size={16} color="var(--accent-indigo)" />
              <span style={{ color: 'var(--accent-indigo)' }}>Ask the Knowledge Graph</span>
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 500 }}>
              Hybrid Vector (k=5) + Graph Traversal (k=6)
            </span>
          </div>

        <div className="brutal-panel-body">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleQuery();
            }}
            className="prompt-box-brutal"
          >
            <div className="prompt-bar-input">
              <div className="prompt-symbol">
                <Search size={18} />
              </div>
              <input
                type="text"
                className="prompt-field"
                placeholder="Ask any research question (e.g., 'How do recent methods mitigate LLM hallucination?')..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
              <button type="submit" className="btn-brutal" disabled={loading}>
                {loading ? (
                  <>
                    <Activity size={16} className="pulse-dot" /> Traversing...
                  </>
                ) : (
                  <>
                    <Search size={16} /> Ask GraphRAG
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Sample Prompts Bar */}
          <div className="sample-prompts-bar">
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>
              Sample Questions:
            </span>
            {SAMPLE_QUESTIONS.map((q, idx) => (
              <button
                key={idx}
                className="sample-chip-brutal"
                onClick={() => {
                  setQuestion(q);
                  handleQuery(q);
                }}
              >
                {q.length > 40 ? q.slice(0, 38) + '...' : q}
              </button>
            ))}
          </div>
        </div>
      </div>
      </TiltCard>

      {/* Error Alert */}
      {error && (
        <div
          className="brutal-panel"
          style={{
            borderColor: 'rgba(225, 29, 72, 0.3)',
            background: 'rgba(225, 29, 72, 0.04)',
            marginBottom: '1.5rem',
          }}
        >
          <div className="brutal-panel-header" style={{ color: 'var(--accent-rose)', background: 'transparent' }}>
            <span>Query Execution Notice</span>
          </div>
          <div className="brutal-panel-body" style={{ color: '#9f1239', fontSize: '0.875rem' }}>
            {error}
          </div>
        </div>
      )}

      {/* Main Split Grid */}
      <div className="dashboard-split-grid">
        {/* Left Column: Synthesized Answer & Details */}
        <section>
          {queryResult ? (
            <TiltCard maxTilt={6} scale={1.01}>
              <div className="brutal-panel" style={{ margin: 0 }}>
                <div className="brutal-panel-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Sparkles size={16} color="var(--accent-indigo)" />
                    <span style={{ color: 'var(--accent-indigo)' }}>Synthesized Answer &amp; Grounded Evidence</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {queryResult.latency_sec && (
                      <span className="badge-brutal cyan">
                        <Clock size={12} /> {queryResult.latency_sec}s
                      </span>
                    )}
                    <button
                      className="btn-brutal-secondary"
                      style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                      onClick={() => copyToClipboard(queryResult.answer)}
                    >
                      {copied ? <Check size={12} color="var(--accent-emerald)" /> : <Copy size={12} />}
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                </div>

                <div className="brutal-panel-body">
                  {/* Synthesized Answer Text */}
                  <div className="answer-lead">
                    {queryResult.answer}
                  </div>

                  {/* Cited Sources */}
                  {queryResult.cited_papers && queryResult.cited_papers.length > 0 && (
                    <div style={{ marginBottom: '1.25rem' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '0.45rem' }}>
                        CITED CORPUS PAPERS ({queryResult.cited_papers.length}):
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                        {queryResult.cited_papers.map((pId) => (
                          <span key={pId} className="badge-brutal purple">
                            <FileText size={11} /> Paper {pId}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Inspection Tabs */}
                  <div style={{ display: 'flex', gap: '0.4rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
                    <button
                      className="btn-brutal-secondary"
                      style={{
                        borderColor: activeTab === 'reasoning' ? 'var(--neon-cyan)' : 'var(--border-subtle)',
                        color: activeTab === 'reasoning' ? '#060813' : 'var(--text-secondary)',
                        background: activeTab === 'reasoning' ? 'var(--neon-cyan)' : 'rgba(255, 255, 255, 0.05)',
                        fontWeight: activeTab === 'reasoning' ? 700 : 500,
                      }}
                      onClick={() => setActiveTab('reasoning')}
                    >
                      <GitBranch size={13} /> Reasoning Path ({queryResult.reasoning_path?.length || 0} Hops)
                    </button>
                    <button
                      className="btn-brutal-secondary"
                      style={{
                        borderColor: activeTab === 'evidence' ? 'var(--neon-cyan)' : 'var(--border-subtle)',
                        color: activeTab === 'evidence' ? '#060813' : 'var(--text-secondary)',
                        background: activeTab === 'evidence' ? 'var(--neon-cyan)' : 'rgba(255, 255, 255, 0.05)',
                        fontWeight: activeTab === 'evidence' ? 700 : 500,
                      }}
                      onClick={() => setActiveTab('evidence')}
                    >
                      <Layers size={13} /> Vector Text Chunks ({queryResult.vector_hits?.length || 0})
                    </button>
                  </div>

                  {/* Tab 1: Reasoning Path */}
                  {activeTab === 'reasoning' && queryResult.reasoning_path && (
                    <div style={{ marginTop: '1rem' }}>
                      {queryResult.reasoning_path.map((step, idx) => (
                        <div key={idx} className="traversal-step">
                          <div className="traversal-idx">#{idx + 1}</div>
                          <div style={{ color: 'var(--text-secondary)', lineHeight: 1.55 }}>{step}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Tab 2: Vector Evidence Hits */}
                  {activeTab === 'evidence' && queryResult.vector_hits && (
                    <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {queryResult.vector_hits.map((v, idx) => (
                        <div key={idx} className="traversal-step" style={{ flexDirection: 'column', gap: '0.4rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', fontSize: '0.75rem' }}>
                            <span style={{ color: 'var(--accent-indigo)', fontWeight: 700 }}>
                              Paper {v.paper_id} &bull; Section: {v.section}
                            </span>
                            <span className="badge-brutal green" style={{ padding: '0.1rem 0.4rem', fontSize: '0.675rem' }}>
                              Score: {v.score?.toFixed(3)}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.5 }}>
                            "{v.text}"
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </TiltCard>
          ) : (
            <TiltCard maxTilt={4} scale={1.005}>
              <div className="brutal-panel" style={{ margin: 0 }}>
                <div className="brutal-panel-header">
                  <span>Query Results &amp; Synthesis</span>
                  <span className="badge-brutal cyan">Ready</span>
                </div>
                <div className="brutal-panel-body" style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--text-muted)' }}>
                  <Sparkles size={36} color="var(--accent-indigo)" style={{ marginBottom: '1rem', opacity: 0.6 }} />
                  <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Ask a question to begin GraphRAG synthesis
                  </div>
                  <div style={{ fontSize: '0.8rem', marginTop: '0.4rem' }}>
                    The engine will execute Cypher path traversal + 384-d vector retrieval and synthesize a cited answer.
                  </div>
                </div>
              </div>
            </TiltCard>
          )}
        </section>

        {/* Right Column: Subgraph Inspector */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
              Subgraph Visualizer
            </div>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {queryResult?.graph_paths && queryResult.graph_paths.length > 0 && (
                <button
                  className="btn-brutal-secondary"
                  style={{ padding: '0.25rem 0.6rem', fontSize: '0.725rem' }}
                  onClick={() => {
                    const pathNodes = [];
                    const pathLinks = [];
                    const seenNodes = new Set();
                    queryResult.graph_paths.forEach((p) => {
                      const sName = p.subject || 'Entity';
                      const oName = p.object || 'Entity';
                      const sId = 'ent_' + sName.toLowerCase().replace(/[^a-z0-9]/g, '_');
                      const oId = 'ent_' + oName.toLowerCase().replace(/[^a-z0-9]/g, '_');
                      if (!seenNodes.has(sId)) {
                        seenNodes.add(sId);
                        pathNodes.push({ id: sId, label: sName, type: p.subject_type || 'Entity' });
                      }
                      if (!seenNodes.has(oId)) {
                        seenNodes.add(oId);
                        pathNodes.push({ id: oId, label: oName, type: p.object_type || 'Entity' });
                      }
                      pathLinks.push({
                        source: sId,
                        target: oId,
                        relation: p.relation || 'RELATED_TO',
                        paper_id: p.paper_id,
                      });
                    });
                    setGraphData({ nodes: pathNodes, links: pathLinks });
                  }}
                >
                  Focus Query Subgraph ({queryResult.graph_paths.length})
                </button>
              )}
              <button
                className="btn-brutal-secondary"
                style={{ padding: '0.25rem 0.6rem', fontSize: '0.725rem' }}
                onClick={onOpenFullGraph}
              >
                <Maximize2 size={12} /> Full-Page Map
              </button>
            </div>
          </div>

          <div style={{ height: '520px' }}>
            <GraphCanvas graphData={graphData} />
          </div>
        </section>
      </div>
    </div>
  );
}
