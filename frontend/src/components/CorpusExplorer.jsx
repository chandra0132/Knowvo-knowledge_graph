import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Search,
  FileText,
  Layers,
  ChevronLeft,
  ChevronRight,
  X,
  ExternalLink,
  ShieldCheck,
  Tag,
  Hash,
  Database,
} from 'lucide-react';

export default function CorpusExplorer() {
  const [papers, setPapers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [paperDetailLoading, setPaperDetailLoading] = useState(false);
  const [paperDetail, setPaperDetail] = useState(null);
  const [detailTab, setDetailTab] = useState('triplets'); // 'triplets' | 'chunks' | 'sections'

  useEffect(() => {
    fetchPapers(page, searchTerm);
  }, [page, pageSize]);

  const fetchPapers = async (pageIdx = 1, query = '') => {
    setLoading(true);
    try {
      const url = query
        ? `/api/papers?page=${pageIdx}&page_size=${pageSize}&search=${encodeURIComponent(query)}`
        : `/api/papers?page=${pageIdx}&page_size=${pageSize}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setPapers(data.papers || []);
        setTotal(data.total || 0);
        setTotalPages(data.total_pages || 1);
        setPage(data.page || 1);
      }
    } catch (e) {
      console.error('Error fetching papers:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchPapers(1, searchTerm);
  };

  const inspectPaper = async (paperId) => {
    setSelectedPaper(paperId);
    setPaperDetailLoading(true);
    setPaperDetail(null);
    try {
      const res = await fetch(`/api/papers/${paperId}`);
      if (res.ok) {
        const data = await res.json();
        setPaperDetail(data);
      }
    } catch (e) {
      console.error('Error fetching paper detail:', e);
    } finally {
      setPaperDetailLoading(false);
    }
  };

  return (
    <div>
      {/* Search & Filter Command Ribbon */}
      <div className="brutal-panel">
        <div className="brutal-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BookOpen size={16} color="var(--accent-indigo)" />
            <span style={{ color: 'var(--accent-indigo)' }}>Corpus &amp; Papers Explorer</span>
          </div>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600 }}>
            {total.toLocaleString()} Papers Indexed
          </span>
        </div>

        <div className="brutal-panel-body">
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <div className="prompt-bar-input" style={{ flex: 1, minWidth: '280px' }}>
              <div className="prompt-symbol"><Search size={16} /></div>
              <input
                type="text"
                className="prompt-field"
                placeholder="Search corpus by arXiv ID (e.g., '2608.05823') or title keywords..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <button type="submit" className="btn-brutal" disabled={loading}>
              Filter Corpus
            </button>
            {searchTerm && (
              <button
                type="button"
                className="btn-brutal-secondary"
                onClick={() => {
                  setSearchTerm('');
                  setPage(1);
                  fetchPapers(1, '');
                }}
              >
                Reset
              </button>
            )}
          </form>
        </div>
      </div>

      {/* Papers Table */}
      <div className="brutal-panel">
        <div className="brutal-panel-header">
          <span>Corpus Inventory Table</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Page {page} of {totalPages} ({total} items)
            </span>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              <button
                className="btn-brutal-secondary"
                style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft size={14} /> Prev
              </button>
              <button
                className="btn-brutal-secondary"
                style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>

        <div className="brutal-panel-body" style={{ padding: 0 }}>
          <div className="brutal-table-container">
            <table className="brutal-table">
              <thead>
                <tr>
                  <th style={{ width: '140px' }}>ArXiv ID</th>
                  <th>Title &amp; Authors</th>
                  <th>Section Outline</th>
                  <th style={{ width: '100px' }}>Chunks</th>
                  <th style={{ width: '110px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--accent-indigo)' }}>
                      Loading corpus data...
                    </td>
                  </tr>
                ) : papers.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                      No matching papers found in corpus.
                    </td>
                  </tr>
                ) : (
                  papers.map((p) => (
                    <tr key={p.paper_id}>
                      <td>
                        <span className="badge-brutal cyan" style={{ fontFamily: 'var(--font-mono)' }}>{p.paper_id}</span>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                          {p.title}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {p.authors && p.authors.length > 0 ? p.authors.join(', ') : 'ArXiv Authors'}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                          {p.sections && p.sections.slice(0, 4).map((s, idx) => (
                            <span key={idx} className="badge-brutal" style={{ fontSize: '0.65rem', background: 'rgba(255, 255, 255, 0.06)', borderColor: 'var(--border-glass)', color: 'var(--text-secondary)' }}>
                              {s}
                            </span>
                          ))}
                          {p.sections && p.sections.length > 4 && (
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                              +{p.sections.length - 4} more
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span style={{ fontWeight: 700, color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                          {p.chunks_count} chunks
                        </span>
                      </td>
                      <td>
                        <button
                          className="btn-brutal-secondary"
                          style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                          onClick={() => inspectPaper(p.paper_id)}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Paper Inspector Modal */}
      {selectedPaper && (
        <div className="brutal-modal-overlay" onClick={() => setSelectedPaper(null)}>
          <div className="brutal-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="brutal-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={18} color="var(--accent-indigo)" />
                <span>Paper Inspector &bull; {selectedPaper}</span>
              </div>
              <button
                onClick={() => setSelectedPaper(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div className="brutal-modal-body">
              {paperDetailLoading ? (
                <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--accent-indigo)' }}>
                  Loading paper contents...
                </div>
              ) : paperDetail ? (
                <div>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
                    {paperDetail.title}
                  </h3>

                  {/* Navigation Tabs */}
                  <div style={{ display: 'flex', gap: '0.4rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem', margin: '1.25rem 0' }}>
                    <button
                      className="btn-brutal-secondary"
                      style={{
                        borderColor: detailTab === 'triplets' ? 'var(--neon-cyan)' : 'var(--border-subtle)',
                        color: detailTab === 'triplets' ? '#060813' : 'var(--text-secondary)',
                        background: detailTab === 'triplets' ? 'var(--neon-cyan)' : 'rgba(255, 255, 255, 0.05)',
                        fontWeight: detailTab === 'triplets' ? 700 : 500,
                      }}
                      onClick={() => setDetailTab('triplets')}
                    >
                      Extracted Triplets ({paperDetail.triplets?.length || 0})
                    </button>
                    <button
                      className="btn-brutal-secondary"
                      style={{
                        borderColor: detailTab === 'chunks' ? 'var(--neon-cyan)' : 'var(--border-subtle)',
                        color: detailTab === 'chunks' ? '#060813' : 'var(--text-secondary)',
                        background: detailTab === 'chunks' ? 'var(--neon-cyan)' : 'rgba(255, 255, 255, 0.05)',
                        fontWeight: detailTab === 'chunks' ? 700 : 500,
                      }}
                      onClick={() => setDetailTab('chunks')}
                    >
                      Text Chunks ({paperDetail.chunks?.length || 0})
                    </button>
                    <button
                      className="btn-brutal-secondary"
                      style={{
                        borderColor: detailTab === 'sections' ? 'var(--neon-cyan)' : 'var(--border-subtle)',
                        color: detailTab === 'sections' ? '#060813' : 'var(--text-secondary)',
                        background: detailTab === 'sections' ? 'var(--neon-cyan)' : 'rgba(255, 255, 255, 0.05)',
                        fontWeight: detailTab === 'sections' ? 700 : 500,
                      }}
                      onClick={() => setDetailTab('sections')}
                    >
                      Section Outline ({paperDetail.sections?.length || 0})
                    </button>
                  </div>

                  {/* Tab 1: Triplets */}
                  {detailTab === 'triplets' && (
                    <div>
                      {paperDetail.triplets && paperDetail.triplets.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                          {paperDetail.triplets.map((t, idx) => (
                            <div key={idx} className="traversal-step" style={{ flexDirection: 'column', gap: '0.35rem' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                                  <span style={{ color: 'var(--neon-cyan)' }}>({t.subject})</span>
                                  {' '}──[{t.relation || 'RELATED_TO'}]──&gt;{' '}
                                  <span style={{ color: 'var(--neon-indigo)' }}>({t.object})</span>
                                </div>
                                <span className="badge-brutal green">Conf: {t.confidence || 0.85}</span>
                              </div>
                              {t.evidence_span && (
                                <div style={{ fontSize: '0.775rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                  Evidence: "{t.evidence_span}"
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                          No standalone extractions file for this paper. Raw triplets were ingested directly into Neo4j graph.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tab 2: Chunks */}
                  {detailTab === 'chunks' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {paperDetail.chunks?.map((c, idx) => (
                        <div key={idx} className="traversal-step" style={{ flexDirection: 'column', gap: '0.35rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--accent-indigo)', fontWeight: 600 }}>
                            <span>Chunk #{idx + 1} &bull; Section: {c.section}</span>
                            <span style={{ fontFamily: 'var(--font-mono)' }}>{c.char_count || c.text?.length || 0} Chars</span>
                          </div>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                            {c.text}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Tab 3: Sections */}
                  {detailTab === 'sections' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {paperDetail.sections?.map((s, idx) => {
                        const sName = typeof s === 'string' ? s : s.section_name || `Section ${idx + 1}`;
                        return (
                          <div key={idx} style={{ padding: '0.75rem 1rem', background: 'rgba(9, 13, 30, 0.75)', border: '1px solid var(--border-glass)', borderRadius: 'var(--radius-sm)' }}>
                            <span style={{ fontWeight: 700, color: 'var(--neon-cyan)' }}>§ {idx + 1}. </span>
                            <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{sName}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ color: 'var(--accent-rose)' }}>Error loading paper details.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
