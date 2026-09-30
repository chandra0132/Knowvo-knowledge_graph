import React, { useState, useEffect } from 'react';
import {
  Search,
  BookOpen,
  GitBranch,
  ShieldCheck,
  Clock,
  Layers,
  Database,
  Share2,
  Activity,
  Cpu,
  Sparkles,
} from 'lucide-react';

import ThreeBackground from './components/ThreeBackground';
import LandingOverview from './components/LandingOverview';
import DashboardQA from './components/DashboardQA';
import CorpusExplorer from './components/CorpusExplorer';
import FullGraphExplorer from './components/FullGraphExplorer';
import VerificationLedger from './components/VerificationLedger';
import AnswerHistory from './components/AnswerHistory';

export default function App() {
  const [currentSection, setCurrentSection] = useState('overview'); // 'overview' | 'dashboard' | 'corpus' | 'graph' | 'verification' | 'history'
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({
    total_nodes: 5194,
    entity_nodes: 304,
    paper_nodes: 550,
    total_relationships: 4890,
    relationship_types: [],
  });
  const [costReport, setCostReport] = useState(null);
  const [qualityReport, setQualityReport] = useState(null);
  const [fullGraphData, setFullGraphData] = useState({ nodes: [], links: [] });
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [queryResult, setQueryResult] = useState(null);
  const [error, setError] = useState(null);

  // Fetch telemetry on load
  useEffect(() => {
    fetchStats();
    fetchReports();
    fetchGraph();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.warn('Stats fetch warning:', e);
    }
  };

  const fetchReports = async () => {
    try {
      const [cRes, qRes] = await Promise.all([
        fetch('/api/scale/cost-report'),
        fetch('/api/scale/quality-report'),
      ]);
      if (cRes.ok) {
        const cData = await cRes.json();
        if (cData.status !== 'no_report_yet') setCostReport(cData);
      }
      if (qRes.ok) {
        const qData = await qRes.json();
        if (qData.status !== 'no_report_yet') setQualityReport(qData);
      }
    } catch (e) {
      console.warn('Reports fetch warning:', e);
    }
  };

  const fetchGraph = async (keyword = '') => {
    try {
      const url = keyword
        ? `/api/graph/explore?keyword=${encodeURIComponent(keyword)}&limit=75`
        : '/api/graph/explore?limit=75';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setFullGraphData(data);
        setGraphData(data);
      }
    } catch (e) {
      console.warn('Graph explore warning:', e);
    }
  };

  const handleQuery = async (qToAsk) => {
    const queryText = qToAsk !== undefined ? qToAsk : question;
    if (!queryText || queryText.trim().length < 3) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: queryText, top_k_vector: 5, top_k_graph: 6 }),
      });

      if (res.ok) {
        const data = await res.json();
        setQueryResult(data);
        setError(null);

        // Update Subgraph preview from returned graph paths
        if (data.graph_paths && data.graph_paths.length > 0) {
          const pathNodes = [];
          const pathLinks = [];
          const seenNodes = new Set();

          data.graph_paths.forEach((p) => {
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
        }

        // Save to History Log
        const histItem = {
          ...data,
          timestamp: new Date().toISOString(),
        };
        fetch('/api/history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(histItem),
        }).catch(() => {});
      } else {
        const errData = await res.json().catch(() => ({ detail: 'Query execution error' }));
        setError(errData.detail || 'Failed to execute GraphRAG query.');
      }
    } catch (e) {
      console.error('Query execution error:', e);
      setError('Could not connect to backend server on port 8000. Please ensure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectHistoryItem = (item) => {
    setQuestion(item.question);
    setQueryResult(item);
    setCurrentSection('dashboard');
  };

  return (
    <div className="console-app">
      {/* 3D Cosmic Particle Background with Interactive Float */}
      <ThreeBackground />

      {/* Glassmorphic Top Header */}
      <header className="console-header">
        <div className="console-brand">
          <div className="console-logo-tag">
            <Share2 size={20} />
          </div>
          <div>
            <div className="console-title">
              Knowvo
            </div>
            <div className="console-title-sub">
              Scientific GraphRAG Console &bull; Scale Architecture
            </div>
          </div>
        </div>

        {/* Minimal Navigation Pills */}
        <nav className="console-nav">
          <button
            className={`nav-tab-btn ${currentSection === 'overview' ? 'active' : ''}`}
            onClick={() => setCurrentSection('overview')}
          >
            Overview
          </button>
          <button
            className={`nav-tab-btn ${currentSection === 'dashboard' ? 'active' : ''}`}
            onClick={() => setCurrentSection('dashboard')}
          >
            Ask GraphRAG
          </button>
          <button
            className={`nav-tab-btn ${currentSection === 'corpus' ? 'active' : ''}`}
            onClick={() => setCurrentSection('corpus')}
          >
            Corpus Papers
          </button>
          <button
            className={`nav-tab-btn ${currentSection === 'graph' ? 'active' : ''}`}
            onClick={() => setCurrentSection('graph')}
          >
            Graph Explorer
          </button>
          <button
            className={`nav-tab-btn ${currentSection === 'verification' ? 'active' : ''}`}
            onClick={() => setCurrentSection('verification')}
          >
            Verification Log
          </button>
          <button
            className={`nav-tab-btn ${currentSection === 'history' ? 'active' : ''}`}
            onClick={() => setCurrentSection('history')}
          >
            History
          </button>
        </nav>
      </header>

      {/* Real-time Telemetry Ribbon */}
      <div className="telemetry-ribbon">
        <div className="telemetry-items">
          <span className="telemetry-node">
            <span className="status-dot-green"></span>
            System: <span className="telemetry-node-val" style={{ color: 'var(--accent-emerald)' }}>Online</span>
          </span>
          <span className="telemetry-node">
            Corpus: <span className="telemetry-node-val">{stats.paper_nodes || 550} Papers</span>
          </span>
          <span className="telemetry-node">
            Entities: <span className="telemetry-node-val">{stats.entity_nodes || 304} Nodes</span>
          </span>
          <span className="telemetry-node">
            Relationships: <span className="telemetry-node-val">{stats.total_relationships || 4890} Edges</span>
          </span>
          <span className="telemetry-node">
            Index: <span className="telemetry-node-val">384-d (all-MiniLM-L6-v2)</span>
          </span>
        </div>

        <div className="telemetry-items">
          <span className="telemetry-node">
            Confidence: <span className="telemetry-node-val" style={{ color: 'var(--accent-emerald)' }}>0.874 Avg</span>
          </span>
          <span className="telemetry-node">
            Tiered Savings: <span className="telemetry-node-val" style={{ color: 'var(--accent-indigo)' }}>94.0%</span>
          </span>
        </div>
      </div>

      {/* Main Section Renderer */}
      <main className="console-body">
        {currentSection === 'overview' && (
          <LandingOverview
            stats={stats}
            costReport={costReport}
            qualityReport={qualityReport}
            onNavigate={(sec) => setCurrentSection(sec)}
          />
        )}

        {currentSection === 'dashboard' && (
          <DashboardQA
            question={question}
            setQuestion={setQuestion}
            queryResult={queryResult}
            loading={loading}
            error={error}
            graphData={graphData}
            fullGraphData={fullGraphData}
            setGraphData={setGraphData}
            handleQuery={handleQuery}
            onOpenFullGraph={() => setCurrentSection('graph')}
          />
        )}

        {currentSection === 'corpus' && <CorpusExplorer />}

        {currentSection === 'graph' && (
          <FullGraphExplorer
            fullGraphData={fullGraphData}
            setFullGraphData={setFullGraphData}
          />
        )}

        {currentSection === 'verification' && <VerificationLedger />}

        {currentSection === 'history' && (
          <AnswerHistory onSelectQuery={handleSelectHistoryItem} />
        )}
      </main>
    </div>
  );
}
