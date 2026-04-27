// frontend/components/CompetitorAnalysis.tsx
'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Network, Clock, Loader2, Link2, AlertTriangle, ExternalLink,
  TrendingDown, RefreshCw, Target, Globe, FileText, ArrowRight,
  ChevronRight, Eye, Zap, Star, Shield, Unlink, Users, Search,
  BarChart3, Trophy, Map as MapIcon, List, X, ZoomIn, ZoomOut, Move,
  GitBranch
} from 'lucide-react';

interface LinkNode {
  url: string; title: string; inbound: number; outbound: number;
  is_hub: boolean; is_orphan: boolean;
}

interface LinkSuggestion {
  from_url: string; to_url: string; anchor_text: string; reason: string;
}

interface LinkingResult {
  total_pages: number; total_internal_links: number;
  hubs: LinkNode[]; orphans: LinkNode[];
  suggestions: LinkSuggestion[];
  avg_links_per_page: number;
}

interface GraphNode {
  id: string;
  url: string;
  title: string;
  inbound: number;
  outbound: number;
  is_hub: boolean;
  is_orphan: boolean;
}

interface GraphEdge {
  source: string;
  target: string;
  anchor: string;
}

interface LinkGraphData {
  domain: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_pages: number;
  total_edges: number;
}

interface DecayItem {
  url: string; title: string; last_modified: string;
  days_since_update: number; decay_risk: string;
  current_position?: number; position_change?: number;
  recommendation: string; competitor_freshness?: string;
}

interface DecayResult {
  total_pages_analyzed: number;
  high_risk: DecayItem[]; medium_risk: DecayItem[]; low_risk: DecayItem[];
  refresh_recommendations: string[];
}

/* ═══════════════════════════════════════════════════════════════
   LinkGraphVisualizer — Pure SVG internal link graph
   ═══════════════════════════════════════════════════════════════ */
function LinkGraphVisualizer({ data }: { data: LinkGraphData }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [size, setSize] = useState({ width: 800, height: 500 });

  // Measure container
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Compute node positions with a simple force-directed layout
  const layout = useMemo(() => {
    const nodes = data.nodes;
    const edges = data.edges;
    if (nodes.length === 0) {
      const emptyPositions: Map<string, { x: number; y: number }> = new Map();
      const emptyRadius: Map<string, number> = new Map();
      return { positions: emptyPositions, nodeRadius: emptyRadius };
    }

    const W = size.width;
    const H = size.height;
    const positions = new Map<string, { x: number; y: number }>();
    const velocities = new Map<string, { x: number; y: number }>();

    // Initialize in a circle
    const centerX = W / 2;
    const centerY = H / 2;
    const radius = Math.min(W, H) * 0.35;
    nodes.forEach((n, i) => {
      const angle = (i / nodes.length) * Math.PI * 2;
      positions.set(n.id, { x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius });
      velocities.set(n.id, { x: 0, y: 0 });
    });

    // Simple force simulation (fixed iterations)
    const k = Math.sqrt((W * H) / (nodes.length + 1)) * 0.8;
    const iterations = 120;
    const maxInbound = Math.max(1, ...nodes.map(n => n.inbound));

    for (let iter = 0; iter < iterations; iter++) {
      // Repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i].id;
          const b = nodes[j].id;
          const pa = positions.get(a)!;
          const pb = positions.get(b)!;
          let dx = pa.x - pb.x;
          let dy = pa.y - pb.y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = (k * k) / dist;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          velocities.get(a)!.x += fx * 0.05;
          velocities.get(a)!.y += fy * 0.05;
          velocities.get(b)!.x -= fx * 0.05;
          velocities.get(b)!.y -= fy * 0.05;
        }
      }

      // Attraction along edges
      for (const e of edges) {
        const pa = positions.get(e.source);
        const pb = positions.get(e.target);
        if (!pa || !pb) continue;
        let dx = pb.x - pa.x;
        let dy = pb.y - pa.y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist * dist) / k;
        const fx = (dx / dist) * force * 0.02;
        const fy = (dy / dist) * force * 0.02;
        velocities.get(e.source)!.x += fx;
        velocities.get(e.source)!.y += fy;
        velocities.get(e.target)!.x -= fx;
        velocities.get(e.target)!.y -= fy;
      }

      // Center gravity
      for (const n of nodes) {
        const p = positions.get(n.id)!;
        const v = velocities.get(n.id)!;
        v.x += (centerX - p.x) * 0.005;
        v.y += (centerY - p.y) * 0.005;
        // Damping
        v.x *= 0.9;
        v.y *= 0.9;
        p.x += v.x;
        p.y += v.y;
        // Keep in bounds
        p.x = Math.max(20, Math.min(W - 20, p.x));
        p.y = Math.max(20, Math.min(H - 20, p.y));
      }
    }

    const nodeRadius = new Map<string, number>();
    for (const n of nodes) {
      const base = 6;
      const scale = Math.sqrt(n.inbound / maxInbound) * 14;
      nodeRadius.set(n.id, Math.max(base, Math.min(28, base + scale)));
    }

    return { positions, nodeRadius };
  }, [data, size.width, size.height]);

  const { positions, nodeRadius } = layout;

  const nodeColor = (n: GraphNode) => {
    if (n.is_hub) return '#4ade80'; // green-400
    if (n.is_orphan) return '#f87171'; // red-400
    return '#60a5fa'; // blue-400
  };

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.max(0.3, Math.min(4, z * delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as Element).tagName === 'circle') return;
    setDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  }, [dragging, dragStart]);

  const handleMouseUp = useCallback(() => setDragging(false), []);

  const zoomIn = () => setZoom(z => Math.min(4, z * 1.2));
  const zoomOut = () => setZoom(z => Math.max(0.3, z / 1.2));
  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const nodeList = useMemo(() => data.nodes, [data]);
  const edgeList = useMemo(() => data.edges, [data]);

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-xs">{data.total_pages} pages · {data.total_edges} links</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={zoomOut} className="bg-white/10 hover:bg-white/20 text-white p-1.5 rounded" title="Zoom out"><ZoomOut className="w-4 h-4" /></button>
          <span className="text-gray-400 text-xs w-12 text-center">{Math.round(zoom * 100)}%</span>
          <button onClick={zoomIn} className="bg-white/10 hover:bg-white/20 text-white p-1.5 rounded" title="Zoom in"><ZoomIn className="w-4 h-4" /></button>
          <button onClick={resetView} className="bg-white/10 hover:bg-white/20 text-white px-2 py-1.5 rounded text-xs" title="Reset view">Reset</button>
        </div>
      </div>

      <div className="flex gap-3 flex-col lg:flex-row">
        {/* Graph canvas */}
        <div
          ref={containerRef}
          className="flex-1 bg-black/40 rounded-xl border border-white/10 relative overflow-hidden cursor-move"
          style={{ height: 520 }}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <svg ref={svgRef} width={size.width} height={size.height} className="absolute inset-0">
            <defs>
              <marker id="arrowhead" markerWidth="6" markerHeight="4" refX="5" refY="2" orient="auto">
                <polygon points="0 0, 6 2, 0 4" fill="#475569" />
              </marker>
            </defs>
            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Edges */}
              {edgeList.map((e, i) => {
                const src = positions.get(e.source);
                const tgt = positions.get(e.target);
                if (!src || !tgt) return null;
                const r = nodeRadius.get(e.target) || 8;
                const dx = tgt.x - src.x;
                const dy = tgt.y - src.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const endX = tgt.x - (dx / dist) * (r + 2);
                const endY = tgt.y - (dy / dist) * (r + 2);
                const isHighlighted = hoveredNode === e.source || hoveredNode === e.target;
                return (
                  <line
                    key={`edge-${i}`}
                    x1={src.x} y1={src.y}
                    x2={endX} y2={endY}
                    stroke={isHighlighted ? '#94a3b8' : '#334155'}
                    strokeWidth={isHighlighted ? 1.5 : 0.8}
                    opacity={hoveredNode && !isHighlighted ? 0.15 : 0.6}
                  />
                );
              })}
              {/* Nodes */}
              {nodeList.map(n => {
                const p = positions.get(n.id);
                if (!p) return null;
                const r = nodeRadius.get(n.id) || 8;
                const isHovered = hoveredNode === n.id;
                const isSelected = selectedNode?.id === n.id;
                return (
                  <g
                    key={n.id}
                    transform={`translate(${p.x}, ${p.y})`}
                    onMouseEnter={() => setHoveredNode(n.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onClick={(e) => { e.stopPropagation(); setSelectedNode(n); }}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle
                      r={r + (isHovered || isSelected ? 3 : 0)}
                      fill={nodeColor(n)}
                      stroke={isSelected ? '#fbbf24' : isHovered ? '#fff' : 'transparent'}
                      strokeWidth={isSelected ? 3 : isHovered ? 2 : 0}
                      opacity={hoveredNode && !isHovered && !isSelected ? 0.3 : 0.9}
                    />
                    {(isHovered || isSelected || r > 14) && (
                      <text
                        y={r + 14}
                        textAnchor="middle"
                        fill="#e2e8f0"
                        fontSize={10}
                        fontWeight={500}
                        style={{ pointerEvents: 'none', textShadow: '0 1px 3px rgba(0,0,0,0.8)' }}
                      >
                        {n.title.length > 28 ? n.title.slice(0, 28) + '…' : n.title}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>

          {/* Legend overlay */}
          <div className="absolute top-3 left-3 bg-black/70 backdrop-blur rounded-lg px-3 py-2 border border-white/10">
            <p className="text-gray-300 text-[10px] font-semibold mb-1.5 uppercase tracking-wider">Legend</p>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
                <span className="text-gray-400 text-[10px]">Hub ({data.nodes.filter(n => n.is_hub).length})</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-400" />
                <span className="text-gray-400 text-[10px]">Normal ({data.nodes.filter(n => !n.is_hub && !n.is_orphan).length})</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
                <span className="text-gray-400 text-[10px]">Orphan ({data.nodes.filter(n => n.is_orphan).length})</span>
              </div>
            </div>
          </div>

          {/* Hint */}
          <div className="absolute bottom-3 right-3 bg-black/50 backdrop-blur rounded px-2 py-1 text-gray-500 text-[10px] flex items-center gap-1">
            <Move className="w-3 h-3" /> Drag to pan · Scroll to zoom · Click node for details
          </div>
        </div>

        {/* Detail panel */}
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="w-full lg:w-72 bg-white/5 rounded-xl border border-white/10 p-4 shrink-0"
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-white font-semibold text-sm flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-orange-400" />
                Page Details
              </h4>
              <button onClick={() => setSelectedNode(null)} className="text-gray-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">URL</p>
                <a href={selectedNode.url} target="_blank" rel="noreferrer" className="text-blue-400 text-xs break-all hover:underline flex items-center gap-1">
                  {selectedNode.url}
                  <ExternalLink className="w-3 h-3 shrink-0" />
                </a>
              </div>
              <div>
                <p className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Title</p>
                <p className="text-white text-xs">{selectedNode.title || '—'}</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-white/5 rounded-lg p-2 text-center">
                  <p className="text-lg font-bold text-green-400">{selectedNode.inbound}</p>
                  <p className="text-[10px] text-gray-500">Incoming</p>
                </div>
                <div className="bg-white/5 rounded-lg p-2 text-center">
                  <p className="text-lg font-bold text-blue-400">{selectedNode.outbound}</p>
                  <p className="text-[10px] text-gray-500">Outgoing</p>
                </div>
              </div>
              <div>
                <p className="text-gray-500 text-[10px] uppercase tracking-wider mb-1">Status</p>
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                  selectedNode.is_hub ? 'bg-green-500/20 text-green-400' :
                  selectedNode.is_orphan ? 'bg-red-500/20 text-red-400' :
                  'bg-blue-500/20 text-blue-400'
                }`}>
                  {selectedNode.is_hub ? 'Hub Page' : selectedNode.is_orphan ? 'Orphan Page' : 'Normal Page'}
                </span>
              </div>
              {/* Connected pages */}
              <div>
                <p className="text-gray-500 text-[10px] uppercase tracking-wider mb-1.5">Links to</p>
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {edgeList.filter(e => e.source === selectedNode.id).slice(0, 10).map((e, i) => (
                    <div key={i} className="text-xs text-gray-400 truncate flex items-center gap-1">
                      <ArrowRight className="w-3 h-3 text-purple-400 shrink-0" />
                      <span className="truncate">{e.target}</span>
                    </div>
                  ))}
                  {edgeList.filter(e => e.source === selectedNode.id).length === 0 && (
                    <p className="text-gray-600 text-xs italic">No outgoing links</p>
                  )}
                </div>
              </div>
              <div>
                <p className="text-gray-500 text-[10px] uppercase tracking-wider mb-1.5">Linked from</p>
                <div className="max-h-32 overflow-y-auto space-y-1">
                  {edgeList.filter(e => e.target === selectedNode.id).slice(0, 10).map((e, i) => (
                    <div key={i} className="text-xs text-gray-400 truncate flex items-center gap-1">
                      <ArrowRight className="w-3 h-3 text-green-400 shrink-0 rotate-180" />
                      <span className="truncate">{e.source}</span>
                    </div>
                  ))}
                  {edgeList.filter(e => e.target === selectedNode.id).length === 0 && (
                    <p className="text-gray-600 text-xs italic">No incoming links</p>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════════════ */
export default function CompetitorAnalysis({ websiteId }: { websiteId: number }) {
  const [activeTab, setActiveTab] = useState<'competitors' | 'linking' | 'linkgraph' | 'decay'>('competitors');
  const [linkingData, setLinkingData] = useState<LinkingResult | null>(null);
  const [linkGraphData, setLinkGraphData] = useState<LinkGraphData | null>(null);
  const [decayData, setDecayData] = useState<DecayResult | null>(null);
  const [linkingLoading, setLinkingLoading] = useState(false);
  const [linkGraphLoading, setLinkGraphLoading] = useState(false);
  const [decayLoading, setDecayLoading] = useState(false);
  const [competitorData, setCompetitorData] = useState<any>(null);
  const [competitorLoading, setCompetitorLoading] = useState(false);
  const [competitorDomain, setCompetitorDomain] = useState('');
  const [expandedOrphan, setExpandedOrphan] = useState<string | null>(null);
  const [linkingView, setLinkingView] = useState<'graph' | 'list'>('list');

  const API = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => {
    setLinkingData(null); setDecayData(null); setLinkGraphData(null);
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API}/api/strategist/${websiteId}/saved`);
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (cancelled) return;
        if (d.linking) setLinkingData(d.linking);
        if (d.decay) setDecayData(d.decay);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [websiteId, API]);

  const runLinking = async () => {
    setLinkingLoading(true); setLinkingData(null);
    try {
      const r = await fetch(`${API}/api/linking/${websiteId}/analyze`, { method: 'POST' });
      if (r.ok) { const d = await r.json(); if (!d.error) setLinkingData(d); }
    } catch {} finally { setLinkingLoading(false); }
  };

  const runLinkGraph = async () => {
    setLinkGraphLoading(true); setLinkGraphData(null);
    try {
      const r = await fetch(`${API}/api/linking/${websiteId}/graph`);
      if (r.ok) { const d = await r.json(); if (!d.error) setLinkGraphData(d); }
    } catch {} finally { setLinkGraphLoading(false); }
  };

  const runDecay = async () => {
    setDecayLoading(true); setDecayData(null);
    try {
      const r = await fetch(`${API}/api/decay/${websiteId}/analyze`, { method: 'POST' });
      if (r.ok) { const d = await r.json(); if (!d.error) setDecayData(d); }
    } catch {} finally { setDecayLoading(false); }
  };

  const runCompetitorAnalysis = async () => {
    if (!competitorDomain.trim()) return;
    setCompetitorLoading(true); setCompetitorData(null);
    try {
      const r = await fetch(`${API}/api/competitors/${websiteId}/research`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ competitor_domain: competitorDomain.trim() })
      });
      if (r.ok) { const d = await r.json(); setCompetitorData(d); }
      else { setCompetitorData({ error: 'Analysis failed. Check the domain and try again.' }); }
    } catch { setCompetitorData({ error: 'Network error' }); }
    finally { setCompetitorLoading(false); }
  };

  const riskColor = (risk: string) => {
    if (risk === 'high') return 'text-red-400 bg-red-500/20';
    if (risk === 'medium') return 'text-yellow-400 bg-yellow-500/20';
    return 'text-green-400 bg-green-500/20';
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <div className="w-9 h-9 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center">
            <Network className="w-5 h-5 text-white" />
          </div>
          Competitors & Site Intelligence
        </h2>
        <p className="text-gray-400 mt-1 text-sm">Competitor research, internal linking, and content freshness</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 flex-wrap">
        {[
          { id: 'competitors' as const, label: 'Competitor Research', icon: Users },
          { id: 'linking' as const, label: 'Hub & Spoke', icon: Network },
          { id: 'linkgraph' as const, label: 'Link Graph', icon: MapIcon },
          { id: 'decay' as const, label: 'Content Decay', icon: Clock },
        ].map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === t.id ? 'bg-orange-500/30 text-white border border-orange-500/50' : 'bg-white/5 text-gray-400 hover:bg-white/10 border border-transparent'
            }`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* ═══ COMPETITOR RESEARCH ═══ */}
      {activeTab === 'competitors' && (
        <div className="space-y-4">
          {/* Quick competitor lookup */}
          <div className="bg-white/5 rounded-xl p-5 border border-white/10">
            <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Search className="w-5 h-5 text-purple-400" /> Analyze a Competitor
            </h3>
            <p className="text-gray-400 text-xs mb-3">Enter a competitor domain to see how they compare on your tracked keywords. This uses the Road to #1 engine to crawl their pages.</p>
            <div className="flex gap-2">
              <input type="text" value={competitorDomain} onChange={e => setCompetitorDomain(e.target.value)}
                placeholder="competitor.com" onKeyDown={e => e.key === 'Enter' && runCompetitorAnalysis()}
                className="flex-1 bg-white/10 border border-white/20 rounded-lg px-4 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500" />
              <button onClick={runCompetitorAnalysis} disabled={competitorLoading || !competitorDomain.trim()}
                className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2">
                {competitorLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Analyze
              </button>
            </div>
          </div>

          {competitorLoading && (
            <div className="bg-purple-500/10 rounded-xl p-8 text-center border border-purple-500/20">
              <Loader2 className="w-10 h-10 text-purple-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Analyzing competitor...</p>
              <p className="text-gray-400 text-sm mt-1">Crawling pages and comparing with your tracked keywords (30-60s)</p>
            </div>
          )}

          {competitorData && !competitorData.error && (
            <div className="space-y-4">
              {competitorData.competitor_analysis && (
                <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-xl p-5 border border-purple-500/20">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-yellow-400" /> Analysis: {competitorDomain}
                  </h3>
                  <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-line">
                    {typeof competitorData.competitor_analysis === 'string'
                      ? competitorData.competitor_analysis
                      : JSON.stringify(competitorData.competitor_analysis, null, 2)}
                  </div>
                </div>
              )}

              {competitorData.strategy && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Target className="w-5 h-5 text-green-400" /> How to Beat Them
                  </h3>
                  <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-line">
                    {typeof competitorData.strategy === 'string'
                      ? competitorData.strategy
                      : JSON.stringify(competitorData.strategy, null, 2)}
                  </div>
                </div>
              )}
            </div>
          )}

          {competitorData?.error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
              <p className="text-red-400 text-sm">{competitorData.error}</p>
            </div>
          )}

          {!competitorData && !competitorLoading && (
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-blue-400" /> How Competitor Research Works
              </h3>
              <div className="space-y-2 text-gray-400 text-sm">
                <p>The competitor analysis engine:</p>
                <p className="ml-3">• Crawls the competitor&apos;s top pages and analyzes their content structure</p>
                <p className="ml-3">• Compares their content against your tracked keywords (Road to #1)</p>
                <p className="ml-3">• Identifies content gaps — topics they cover that you don&apos;t</p>
                <p className="ml-3">• Generates specific recommendations to outrank them</p>
                <p className="mt-2 text-gray-500">For deeper keyword-level competitor analysis, use <strong className="text-purple-400">Road to #1</strong> — it crawls the top 3 competitors for each tracked keyword.</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ HUB & SPOKE LINKING ═══ */}
      {activeTab === 'linking' && (
        <div className="space-y-4">
          {!linkingData && !linkingLoading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <Network className="w-14 h-14 text-orange-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Analyze Internal Linking</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                Crawls your site to map the internal link graph. Finds hub pages, orphaned pages, and suggests new links to build topical authority.
              </p>
              <button onClick={runLinking}
                className="bg-gradient-to-r from-orange-500 to-red-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Run Link Analysis
              </button>
            </div>
          )}

          {linkingLoading && (
            <div className="bg-orange-500/10 rounded-xl p-8 text-center border border-orange-500/20">
              <Loader2 className="w-10 h-10 text-orange-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Crawling site and mapping internal links...</p>
              <p className="text-gray-400 text-sm mt-1">This may take 30-60 seconds</p>
            </div>
          )}

          {linkingData && (
            <div className="space-y-4">
              {/* View toggle */}
              <div className="flex items-center justify-between">
                <div className="flex bg-white/5 rounded-lg p-0.5 border border-white/10">
                  <button
                    onClick={() => setLinkingView('list')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-all ${
                      linkingView === 'list' ? 'bg-orange-500/30 text-white' : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    <List className="w-3.5 h-3.5" /> List View
                  </button>
                  <button
                    onClick={() => setLinkingView('graph')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-all ${
                      linkingView === 'graph' ? 'bg-orange-500/30 text-white' : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    <MapIcon className="w-3.5 h-3.5" /> Graph View
                  </button>
                </div>
                <button onClick={runLinking} className="text-gray-400 hover:text-white text-xs flex items-center gap-1">
                  <RefreshCw className="w-3.5 h-3.5" /> Re-analyze
                </button>
              </div>

              {linkingView === 'graph' ? (
                /* Graph placeholder — prompts user to use Link Graph tab for full viz */
                <div className="bg-white/5 rounded-xl p-8 border border-white/10 text-center">
                  <MapIcon className="w-10 h-10 text-orange-400 mx-auto mb-3 opacity-60" />
                  <p className="text-white font-medium mb-1">Interactive Graph Available</p>
                  <p className="text-gray-400 text-sm mb-4">Switch to the <strong className="text-orange-400">Link Graph</strong> tab for the full interactive visualization with zoom, pan, and node details.</p>
                  <button onClick={() => setActiveTab('linkgraph')} className="bg-orange-500/20 text-orange-400 border border-orange-500/30 px-4 py-2 rounded-lg text-sm font-medium hover:bg-orange-500/30 transition-all">
                    Open Link Graph
                  </button>
                </div>
              ) : (
                <>
                  {/* Summary stats */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { l: 'Pages Crawled', v: linkingData.total_pages, c: 'text-white' },
                      { l: 'Internal Links', v: linkingData.total_internal_links, c: 'text-blue-400' },
                      { l: 'Hub Pages', v: linkingData.hubs?.length || 0, c: 'text-green-400' },
                      { l: 'Orphan Pages', v: linkingData.orphans?.length || 0, c: 'text-red-400' },
                    ].map(s => (
                      <div key={s.l} className="bg-white/5 rounded-xl p-4 text-center border border-white/10">
                        <p className={`text-2xl font-bold ${s.c}`}>{s.v}</p>
                        <p className="text-[10px] text-gray-500 mt-1">{s.l}</p>
                      </div>
                    ))}
                  </div>

                  {/* Avg links per page */}
                  <div className="bg-white/5 rounded-lg px-4 py-2 border border-white/10 flex items-center justify-between">
                    <span className="text-gray-400 text-sm">Avg links per page</span>
                    <span className={`font-bold ${(linkingData.avg_links_per_page || 0) >= 3 ? 'text-green-400' : 'text-yellow-400'}`}>
                      {(linkingData.avg_links_per_page || 0).toFixed(1)}
                    </span>
                  </div>

                  {/* Hub Pages */}
                  {linkingData.hubs?.length > 0 && (
                    <div className="bg-green-500/5 rounded-xl p-5 border border-green-500/20">
                      <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                        <Star className="w-5 h-5 text-green-400" /> Hub Pages (Strong Authority)
                      </h3>
                      {linkingData.hubs.slice(0, 10).map((hub, i) => (
                        <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <Star className="w-3.5 h-3.5 text-green-400 shrink-0" />
                            <div className="min-w-0">
                              <p className="text-white text-sm truncate">{hub.title || hub.url}</p>
                              <p className="text-gray-500 text-[10px] truncate">{hub.url}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3 shrink-0 ml-3">
                            <span className="text-green-400 text-xs">{hub.inbound} in</span>
                            <span className="text-blue-400 text-xs">{hub.outbound} out</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Orphan Pages */}
                  {linkingData.orphans?.length > 0 && (
                    <div className="bg-red-500/5 rounded-xl p-5 border border-red-500/20">
                      <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                        <Unlink className="w-5 h-5 text-red-400" /> Orphan Pages (No Internal Links)
                      </h3>
                      <p className="text-gray-400 text-xs mb-3">These pages have no or very few internal links pointing to them. Search engines may not discover or value them.</p>
                      {linkingData.orphans.slice(0, 15).map((orphan, i) => (
                        <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
                          <div className="min-w-0 flex-1">
                            <p className="text-white text-sm truncate">{orphan.title || orphan.url}</p>
                            <p className="text-gray-500 text-[10px] truncate">{orphan.url}</p>
                          </div>
                          <span className="text-red-400 text-xs shrink-0 ml-2">{orphan.inbound} links in</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Link Suggestions */}
                  {linkingData.suggestions?.length > 0 && (
                    <div className="bg-purple-500/5 rounded-xl p-5 border border-purple-500/20">
                      <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                        <Link2 className="w-5 h-5 text-purple-400" /> Suggested Internal Links
                      </h3>
                      {linkingData.suggestions.slice(0, 10).map((sug, i) => (
                        <div key={i} className="bg-white/5 rounded-lg p-3 mb-2">
                          <div className="flex items-center gap-2 text-sm">
                            <span className="text-gray-300 truncate flex-1">{sug.from_url}</span>
                            <ArrowRight className="w-3 h-3 text-purple-400 shrink-0" />
                            <span className="text-purple-400 truncate flex-1">{sug.to_url}</span>
                          </div>
                          <div className="flex items-center gap-3 mt-1.5">
                            <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">&quot;{sug.anchor_text}&quot;</span>
                            <span className="text-gray-500 text-xs">{sug.reason}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              <button onClick={runLinking} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4" /> Re-analyze
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ LINK GRAPH ═══ */}
      {activeTab === 'linkgraph' && (
        <div className="space-y-4">
          {!linkGraphData && !linkGraphLoading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <MapIcon className="w-14 h-14 text-orange-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Visualize Link Graph</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                Explore your site&apos;s internal link structure as an interactive graph. Click nodes to inspect pages, zoom and pan to navigate.
              </p>
              <button onClick={runLinkGraph}
                className="bg-gradient-to-r from-orange-500 to-red-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Load Link Graph
              </button>
            </div>
          )}

          {linkGraphLoading && (
            <div className="bg-orange-500/10 rounded-xl p-8 text-center border border-orange-500/20">
              <Loader2 className="w-10 h-10 text-orange-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Building link graph...</p>
              <p className="text-gray-400 text-sm mt-1">Crawling pages and computing layout</p>
            </div>
          )}

          {linkGraphData && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MapIcon className="w-4 h-4 text-orange-400" />
                  <span className="text-white font-medium text-sm">{linkGraphData.domain}</span>
                </div>
                <button onClick={runLinkGraph} className="text-gray-400 hover:text-white text-xs flex items-center gap-1">
                  <RefreshCw className="w-3.5 h-3.5" /> Refresh
                </button>
              </div>
              <LinkGraphVisualizer data={linkGraphData} />
            </div>
          )}
        </div>
      )}

      {/* ═══ CONTENT DECAY ═══ */}
      {activeTab === 'decay' && (
        <div className="space-y-4">
          {!decayData && !decayLoading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <Clock className="w-14 h-14 text-yellow-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Detect Content Decay</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                Checks page freshness, identifies content that&apos;s losing rankings, and recommends updates to regain positions.
              </p>
              <button onClick={runDecay}
                className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Run Decay Analysis
              </button>
            </div>
          )}

          {decayLoading && (
            <div className="bg-yellow-500/10 rounded-xl p-8 text-center border border-yellow-500/20">
              <Loader2 className="w-10 h-10 text-yellow-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Analyzing content freshness...</p>
            </div>
          )}

          {decayData && (
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { l: 'Pages Analyzed', v: decayData.total_pages_analyzed, c: 'text-white' },
                  { l: 'High Risk', v: decayData.high_risk?.length || 0, c: 'text-red-400' },
                  { l: 'Medium Risk', v: decayData.medium_risk?.length || 0, c: 'text-yellow-400' },
                  { l: 'Low Risk', v: decayData.low_risk?.length || 0, c: 'text-green-400' },
                ].map(s => (
                  <div key={s.l} className="bg-white/5 rounded-xl p-4 text-center border border-white/10">
                    <p className={`text-2xl font-bold ${s.c}`}>{s.v}</p>
                    <p className="text-[10px] text-gray-500 mt-1">{s.l}</p>
                  </div>
                ))}
              </div>

              {/* Decay items by risk */}
              {['high', 'medium', 'low'].map(risk => {
                const items: DecayItem[] = risk === 'high' ? (decayData.high_risk || []) : risk === 'medium' ? (decayData.medium_risk || []) : (decayData.low_risk || []);
                if (!items.length) return null;
                const colors = { high: { bg: 'bg-red-500/5', border: 'border-red-500/20', text: 'text-red-400', icon: AlertTriangle },
                  medium: { bg: 'bg-yellow-500/5', border: 'border-yellow-500/20', text: 'text-yellow-400', icon: Clock },
                  low: { bg: 'bg-green-500/5', border: 'border-green-500/20', text: 'text-green-400', icon: Shield } };
                const c = colors[risk as keyof typeof colors];
                const Icon = c.icon;
                return (
                  <div key={risk} className={`${c.bg} rounded-xl p-5 ${c.border} border`}>
                    <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                      <Icon className={`w-5 h-5 ${c.text}`} /> {risk.charAt(0).toUpperCase() + risk.slice(1)} Risk ({items.length})
                    </h3>
                    {items.slice(0, 8).map((item, i) => (
                      <div key={i} className="bg-white/5 rounded-lg p-3 mb-2">
                        <div className="flex items-start justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="text-white text-sm truncate">{item.title || item.url}</p>
                            <p className="text-gray-500 text-[10px] truncate">{item.url}</p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0 ml-3">
                            <span className={`text-xs px-1.5 py-0.5 rounded ${riskColor(item.decay_risk)}`}>{item.days_since_update}d old</span>
                            {item.position_change && item.position_change < 0 && (
                              <span className="text-red-400 text-xs flex items-center gap-0.5">
                                <TrendingDown className="w-3 h-3" /> {Math.abs(item.position_change)}
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="text-gray-400 text-xs mt-1.5">{item.recommendation}</p>
                      </div>
                    ))}
                  </div>
                );
              })}

              {/* Refresh recommendations */}
              {decayData.refresh_recommendations?.length > 0 && (
                <div className="bg-purple-500/10 rounded-xl p-5 border border-purple-500/20">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Zap className="w-5 h-5 text-purple-400" /> AI Recommendations
                  </h3>
                  {decayData.refresh_recommendations.map((rec, i) => (
                    <div key={i} className="flex items-start gap-2 mb-2">
                      <span className="text-purple-400 text-xs font-bold bg-purple-500/20 px-1.5 py-0.5 rounded shrink-0">{i+1}</span>
                      <p className="text-gray-300 text-sm">{rec}</p>
                    </div>
                  ))}
                </div>
              )}

              <button onClick={runDecay} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4" /> Re-analyze
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
