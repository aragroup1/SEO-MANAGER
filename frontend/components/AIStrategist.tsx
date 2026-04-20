// frontend/components/AIStrategist.tsx
'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Send, Loader2, User, Bot, Sparkles, Map,
  AlertTriangle, TrendingUp, Target, FileText, X,
  MessageSquare, Lightbulb, ChevronDown, Zap, Calendar,
  CheckCircle, Shield, Star, Clock, ArrowRight, Trophy,
  ChevronRight, Flag, Layers, BarChart3
} from 'lucide-react';

interface Message { role: 'user' | 'assistant'; content: string; timestamp: string; }

export default function AIStrategist({ websiteId }: { websiteId: number }) {
  const [activeMode, setActiveMode] = useState<'strategy' | 'weekly' | 'portfolio' | 'chat'>('strategy');
  const [strategy, setStrategy] = useState<any>(null);
  const [weeklyPlan, setWeeklyPlan] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const API = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => {
    setStrategy(null); setWeeklyPlan(null); setPortfolio(null); setMessages([]);
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API}/api/strategist/${websiteId}/saved`);
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (cancelled) return;
        if (d.strategy) setStrategy({ ...d.strategy, generated_at: d.strategy_generated_at });
        if (d.weekly_plan) setWeeklyPlan({ ...d.weekly_plan, generated_at: d.weekly_generated_at });
        if (d.portfolio) setPortfolio({ ...d.portfolio, generated_at: d.portfolio_generated_at });
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [websiteId, API]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const generateStrategy = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/strategist/${websiteId}/generate-strategy`, { method: 'POST' });
      if (r.ok) { const d = await r.json(); setStrategy(d); }
    } catch {} finally { setLoading(false); }
  };

  const generateWeekly = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/strategist/${websiteId}/weekly-plan`, { method: 'POST' });
      if (r.ok) { const d = await r.json(); setWeeklyPlan(d); }
    } catch {} finally { setLoading(false); }
  };

  const fetchPortfolio = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/strategist/${websiteId}/portfolio`);
      if (r.ok) { const d = await r.json(); setPortfolio(d); }
    } catch {} finally { setLoading(false); }
  };

  const sendMessage = async () => {
    const msg = input.trim();
    if (!msg || chatLoading) return;
    const userMsg: Message = { role: 'user', content: msg, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setChatLoading(true);
    try {
      const r = await fetch(`${API}/api/strategist/${websiteId}/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history: messages.map(m => ({ role: m.role, content: m.content })) })
      });
      if (r.ok) {
        const d = await r.json();
        setMessages(prev => [...prev, { role: 'assistant', content: d.response || d.error || 'No response', timestamp: new Date().toISOString() }]);
      }
    } catch {} finally { setChatLoading(false); }
  };

  const formatText = (text: string) => text.split('\n').map((line, i) => {
    line = line.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>');
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) return <p key={i} className="ml-4 mb-1" dangerouslySetInnerHTML={{ __html: '&bull; ' + line.trim().substring(2) }} />;
    const num = line.trim().match(/^(\d+)\.\s(.*)/);
    if (num) return <p key={i} className="ml-4 mb-1" dangerouslySetInnerHTML={{ __html: `<span class="text-purple-400 font-bold">${num[1]}.</span> ${num[2]}` }} />;
    if (!line.trim()) return <br key={i} />;
    return <p key={i} className="mb-1" dangerouslySetInnerHTML={{ __html: line }} />;
  });

  const modes = [
    { id: 'strategy' as const, label: 'Master Strategy', icon: Map, desc: 'The big picture plan' },
    { id: 'weekly' as const, label: 'Weekly Plan', icon: Calendar, desc: "This week's actions" },
    { id: 'portfolio' as const, label: 'Portfolio', icon: Layers, desc: 'Keyword priorities' },
    { id: 'chat' as const, label: 'Chat', icon: MessageSquare, desc: 'Ask anything' },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-lg flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            AI SEO Strategist
          </h2>
          <p className="text-gray-400 mt-1 text-sm">Your SEO general — sees the whole battlefield</p>
        </div>
      </div>

      {/* Mode Tabs */}
      <div className="flex gap-2">
        {modes.map(m => (
          <button key={m.id} onClick={() => { setActiveMode(m.id); if (m.id === 'portfolio' && !portfolio) fetchPortfolio(); }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeMode === m.id ? 'bg-purple-500/30 text-white border border-purple-500/50' : 'bg-white/5 text-gray-400 hover:bg-white/10 border border-transparent'
            }`}>
            <m.icon className="w-4 h-4" />
            <span className="hidden md:inline">{m.label}</span>
          </button>
        ))}
      </div>

      {/* ═══ MASTER STRATEGY ═══ */}
      {activeMode === 'strategy' && (
        <div className="space-y-4">
          {!strategy && !loading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <Map className="w-14 h-14 text-purple-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Generate Master Strategy</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                The AI will analyze ALL your data — audit, keywords, tracked keywords, fixes, competitors — and create a comprehensive battle plan.
              </p>
              <button onClick={generateStrategy}
                className="bg-gradient-to-r from-purple-500 to-cyan-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Generate Strategy
              </button>
            </div>
          )}

          {loading && (
            <div className="bg-purple-500/10 rounded-xl p-8 text-center border border-purple-500/20">
              <Loader2 className="w-10 h-10 text-purple-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Analyzing all data and generating strategy...</p>
              <p className="text-gray-400 text-sm mt-1">This takes 15-30 seconds</p>
            </div>
          )}

          {strategy?.strategy && (
            <div className="space-y-4">
              {/* Executive Summary */}
              <div className="bg-gradient-to-r from-purple-500/15 to-cyan-500/15 rounded-xl p-5 border border-purple-500/20">
                <h3 className="text-white font-semibold mb-2 flex items-center gap-2"><Flag className="w-4 h-4 text-purple-400" /> Executive Summary</h3>
                <p className="text-gray-300 text-sm leading-relaxed">{strategy.strategy.executive_summary}</p>
              </div>

              {/* SWOT */}
              {strategy.strategy.current_state && (
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: 'strengths', label: 'Strengths', color: 'green', icon: CheckCircle },
                    { key: 'weaknesses', label: 'Weaknesses', color: 'red', icon: AlertTriangle },
                    { key: 'opportunities', label: 'Opportunities', color: 'cyan', icon: TrendingUp },
                    { key: 'threats', label: 'Threats', color: 'orange', icon: Shield },
                  ].map(s => (
                    <div key={s.key} className={`bg-${s.color}-500/5 rounded-xl p-4 border border-${s.color}-500/20`}>
                      <h4 className={`text-${s.color}-400 font-medium text-sm mb-2 flex items-center gap-1.5`}>
                        <s.icon className="w-3.5 h-3.5" /> {s.label}
                      </h4>
                      <ul className="space-y-1">
                        {(strategy.strategy.current_state[s.key] || []).map((item: string, i: number) => (
                          <li key={i} className="text-gray-300 text-xs flex items-start gap-1.5">
                            <span className="text-gray-600 mt-0.5">•</span> {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}

              {/* Strategic Goals */}
              {strategy.strategy.strategic_goals?.length > 0 && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Target className="w-4 h-4 text-green-400" /> Strategic Goals</h3>
                  <div className="space-y-2">
                    {strategy.strategy.strategic_goals.map((g: any, i: number) => (
                      <div key={i} className="bg-white/5 rounded-lg p-3 flex items-start gap-3">
                        <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded font-bold shrink-0">#{g.priority || i+1}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium">{g.goal}</p>
                          <div className="flex items-center gap-3 mt-1">
                            <span className="text-xs text-green-400">{g.target}</span>
                            <span className="text-xs text-gray-500">{g.timeframe}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Keyword Portfolio */}
              {strategy.strategy.keyword_portfolio && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Star className="w-4 h-4 text-yellow-400" /> Keyword Portfolio Strategy</h3>
                  {strategy.strategy.keyword_portfolio.primary_keywords?.length > 0 && (
                    <div className="mb-3">
                      <p className="text-yellow-400 text-xs font-medium mb-1.5">PRIMARY FOCUS (most effort here)</p>
                      {strategy.strategy.keyword_portfolio.primary_keywords.map((k: string, i: number) => (
                        <p key={i} className="text-gray-300 text-sm ml-3 mb-0.5">• {k}</p>
                      ))}
                    </div>
                  )}
                  {strategy.strategy.keyword_portfolio.cannibalization_fixes?.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/10">
                      <p className="text-red-400 text-xs font-medium mb-1.5">CANNIBALIZATION FIXES</p>
                      {strategy.strategy.keyword_portfolio.cannibalization_fixes.map((f: string, i: number) => (
                        <p key={i} className="text-gray-300 text-sm ml-3 mb-0.5">• {f}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* This Week */}
              {strategy.strategy.weekly_focus && (
                <div className="bg-gradient-to-r from-green-500/10 to-emerald-500/10 rounded-xl p-5 border border-green-500/20">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Zap className="w-4 h-4 text-green-400" /> This Week</h3>
                  {strategy.strategy.weekly_focus.this_week?.map((a: string, i: number) => (
                    <div key={i} className="flex items-start gap-2 mb-2">
                      <span className="text-green-400 text-xs font-bold bg-green-500/20 px-1.5 py-0.5 rounded shrink-0">{i+1}</span>
                      <p className="text-gray-300 text-sm">{a}</p>
                    </div>
                  ))}
                  {strategy.strategy.weekly_focus.quick_wins?.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-green-500/20">
                      <p className="text-yellow-400 text-xs font-medium mb-1.5">QUICK WINS (&lt;1 hour)</p>
                      {strategy.strategy.weekly_focus.quick_wins.map((w: string, i: number) => (
                        <p key={i} className="text-gray-300 text-sm ml-3 mb-0.5">• {w}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Monthly Milestones */}
              {strategy.strategy.monthly_milestones?.length > 0 && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Calendar className="w-4 h-4 text-blue-400" /> Monthly Milestones</h3>
                  <div className="space-y-3">
                    {strategy.strategy.monthly_milestones.map((m: any, i: number) => (
                      <div key={i} className="bg-white/5 rounded-lg p-3">
                        <p className="text-blue-400 text-xs font-bold mb-1">MONTH {m.month}</p>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <p className="text-gray-500 text-[10px] mb-1">TARGETS</p>
                            {(m.targets || []).map((t: string, j: number) => (
                              <p key={j} className="text-gray-300 text-xs mb-0.5">• {t}</p>
                            ))}
                          </div>
                          <div>
                            <p className="text-gray-500 text-[10px] mb-1">KEY ACTIONS</p>
                            {(m.actions || []).map((a: string, j: number) => (
                              <p key={j} className="text-gray-300 text-xs mb-0.5">• {a}</p>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Technical Priorities */}
              {strategy.strategy.technical_priorities?.length > 0 && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Sparkles className="w-4 h-4 text-purple-400" /> Technical Priorities</h3>
                  {strategy.strategy.technical_priorities.map((t: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 mb-2 bg-white/5 rounded-lg px-3 py-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${t.impact === 'high' ? 'bg-red-500/20 text-red-400' : t.impact === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>{t.impact}</span>
                      <p className="text-gray-300 text-sm flex-1">{t.action}</p>
                      <span className="text-xs text-gray-500">{t.effort}</span>
                    </div>
                  ))}
                </div>
              )}

              <button onClick={generateStrategy} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 transition-all flex items-center justify-center gap-2">
                <Brain className="w-4 h-4" /> Regenerate Strategy
              </button>
            </div>
          )}

          {strategy?.error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
              <p className="text-red-400 text-sm">{strategy.error}</p>
            </div>
          )}
        </div>
      )}

      {/* ═══ WEEKLY PLAN ═══ */}
      {activeMode === 'weekly' && (
        <div className="space-y-4">
          {!weeklyPlan && !loading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <Calendar className="w-14 h-14 text-green-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Generate Weekly Action Plan</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                Get a specific list of what to work on THIS week, based on your current data and priorities.
              </p>
              <button onClick={generateWeekly}
                className="bg-gradient-to-r from-green-500 to-emerald-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Generate This Week's Plan
              </button>
            </div>
          )}

          {loading && (
            <div className="bg-green-500/10 rounded-xl p-8 text-center border border-green-500/20">
              <Loader2 className="w-10 h-10 text-green-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Building your weekly plan...</p>
            </div>
          )}

          {weeklyPlan?.plan && (
            <div className="space-y-4">
              <div className="bg-gradient-to-r from-green-500/15 to-emerald-500/15 rounded-xl p-5 border border-green-500/20">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-white font-semibold flex items-center gap-2"><Calendar className="w-4 h-4 text-green-400" /> Week of {weeklyPlan.plan.week_of}</h3>
                  {weeklyPlan.plan.priority_score && <span className="text-xs bg-white/10 text-gray-300 px-2 py-1 rounded">Urgency: {weeklyPlan.plan.priority_score}/10</span>}
                </div>
                <p className="text-gray-300 text-sm">{weeklyPlan.plan.summary}</p>
              </div>

              {weeklyPlan.plan.critical_actions?.length > 0 && (
                <div className="bg-red-500/5 rounded-xl p-5 border border-red-500/20">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-red-400" /> Critical Actions</h4>
                  {weeklyPlan.plan.critical_actions.map((a: any, i: number) => (
                    <div key={i} className="bg-white/5 rounded-lg p-3 mb-2">
                      <p className="text-white text-sm font-medium">{a.task}</p>
                      <p className="text-gray-400 text-xs mt-1">{a.why}</p>
                      <div className="flex gap-3 mt-1">
                        <span className="text-xs text-gray-500">{a.estimated_time}</span>
                        <span className="text-xs text-green-400">{a.expected_impact}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {weeklyPlan.plan.keyword_work?.length > 0 && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><Target className="w-4 h-4 text-yellow-400" /> Keyword Work</h4>
                  {weeklyPlan.plan.keyword_work.map((k: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 mb-2 bg-white/5 rounded-lg px-3 py-2">
                      <span className="text-yellow-400 text-sm font-bold shrink-0">#{k.current_position || '?'}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm truncate">{k.keyword}</p>
                        <p className="text-gray-400 text-xs">{k.action}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {weeklyPlan.plan.technical_fixes?.length > 0 && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><Sparkles className="w-4 h-4 text-purple-400" /> Technical Fixes</h4>
                  {weeklyPlan.plan.technical_fixes.map((f: any, i: number) => (
                    <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
                      <p className="text-gray-300 text-sm">{f.fix}</p>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${f.priority === 'critical' ? 'bg-red-500/20 text-red-400' : f.priority === 'high' ? 'bg-orange-500/20 text-orange-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{f.priority}</span>
                    </div>
                  ))}
                </div>
              )}

              <button onClick={generateWeekly} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 transition-all flex items-center justify-center gap-2">
                <Calendar className="w-4 h-4" /> Regenerate Plan
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ PORTFOLIO ═══ */}
      {activeMode === 'portfolio' && (
        <div className="space-y-4">
          {!portfolio && !loading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <Layers className="w-14 h-14 text-yellow-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Keyword Portfolio Analysis</h3>
              <p className="text-gray-400 text-sm mb-6">Analyze your tracked keywords for conflicts, priorities, and gaps.</p>
              <button onClick={fetchPortfolio}
                className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Analyze Portfolio
              </button>
            </div>
          )}

          {loading && (
            <div className="bg-yellow-500/10 rounded-xl p-8 text-center border border-yellow-500/20">
              <Loader2 className="w-10 h-10 text-yellow-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Analyzing keyword portfolio...</p>
            </div>
          )}

          {portfolio && !portfolio.error && (
            <div className="space-y-4">
              <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 rounded-xl p-5 border border-yellow-500/20">
                <h3 className="text-white font-semibold mb-1 flex items-center gap-2"><Layers className="w-4 h-4 text-yellow-400" /> Portfolio: {portfolio.portfolio_size} Keywords</h3>
                {portfolio.recommendations?.focus_keywords?.length > 0 && (
                  <p className="text-gray-400 text-sm">Focus on: <span className="text-yellow-400">{portfolio.recommendations.focus_keywords.join(', ')}</span></p>
                )}
              </div>

              {/* Priority ranked keywords */}
              {portfolio.priorities?.length > 0 && (
                <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                  <h4 className="text-white font-medium text-sm mb-3">Priority Ranking</h4>
                  {portfolio.priorities.map((p: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 mb-2 bg-white/5 rounded-lg px-3 py-2.5">
                      <span className={`text-xs font-bold w-6 text-center ${i < 3 ? 'text-yellow-400' : 'text-gray-500'}`}>#{i+1}</span>
                      <Star className={`w-3.5 h-3.5 shrink-0 ${i < 3 ? 'text-yellow-400 fill-yellow-400' : 'text-gray-600'}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm truncate">{p.keyword}</p>
                        <p className="text-gray-500 text-xs truncate">{p.target_url || 'No target URL'}</p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className={`text-sm font-bold ${p.position ? (p.position <= 10 ? 'text-green-400' : p.position <= 20 ? 'text-yellow-400' : 'text-orange-400') : 'text-gray-500'}`}>
                          {p.position ? `#${p.position}` : 'N/R'}
                        </span>
                        <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-yellow-500 to-green-500 rounded-full" style={{ width: `${Math.min(p.priority_score, 100)}%` }} />
                        </div>
                        <span className="text-xs text-gray-400 w-8 text-right">{p.priority_score}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Conflicts */}
              {portfolio.conflicts?.length > 0 && (
                <div className="bg-red-500/5 rounded-xl p-5 border border-red-500/20">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-red-400" /> Conflicts Detected</h4>
                  {portfolio.conflicts.map((c: any, i: number) => (
                    <div key={i} className="bg-white/5 rounded-lg p-3 mb-2">
                      <p className="text-red-400 text-xs font-medium mb-1">{c.type === 'same_target_url' ? 'Same Target URL' : c.type}</p>
                      <p className="text-white text-sm">{c.keywords?.join(' vs ')}</p>
                      <p className="text-gray-400 text-xs mt-1">{c.recommendation}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Cannibalization */}
              {portfolio.cannibalization?.length > 0 && (
                <div className="bg-orange-500/5 rounded-xl p-5 border border-orange-500/20">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-orange-400" /> Cannibalization ({portfolio.cannibalization.length})</h4>
                  {portfolio.cannibalization.slice(0, 5).map((c: any, i: number) => (
                    <div key={i} className="bg-white/5 rounded-lg p-3 mb-2">
                      <p className="text-white text-sm font-medium">"{c.keyword}"</p>
                      {c.pages?.map((p: any, j: number) => (
                        <p key={j} className="text-gray-400 text-xs ml-3">• {p.page} (pos {p.position})</p>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              <button onClick={fetchPortfolio} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 transition-all flex items-center justify-center gap-2">
                <Layers className="w-4 h-4" /> Refresh Analysis
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ CHAT ═══ */}
      {activeMode === 'chat' && (
        <div className="bg-white/5 rounded-2xl border border-white/10 overflow-hidden" style={{ height: 'calc(100vh - 220px)', minHeight: '400px' }}>
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="text-center py-8">
                  <Brain className="w-12 h-12 text-purple-400 mx-auto mb-3 opacity-50" />
                  <h3 className="text-white font-semibold mb-2">Strategic Chat</h3>
                  <p className="text-gray-500 text-sm mb-4 max-w-md mx-auto">I have your full audit data, keyword rankings, tracked keywords, and fix history. Ask me anything about your SEO strategy.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-lg mx-auto">
                    {[
                      { icon: TrendingUp, label: 'What should I prioritize?', q: 'Based on all my data, what are the top 3 priorities right now?' },
                      { icon: Target, label: 'Keyword opportunities', q: 'Which keywords am I closest to page 1 for? What would push them over?' },
                      { icon: AlertTriangle, label: 'Biggest risks', q: 'What are the biggest risks to my rankings right now?' },
                      { icon: Lightbulb, label: 'Quick wins', q: 'What can I do today that will have the fastest SEO impact?' },
                    ].map((qp, i) => (
                      <button key={i} onClick={() => setInput(qp.q)}
                        className="flex items-center gap-2 text-left p-3 bg-white/5 hover:bg-white/10 rounded-lg border border-white/10 transition-all">
                        <qp.icon className="w-4 h-4 text-purple-400 shrink-0" />
                        <span className="text-gray-300 text-xs">{qp.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  {msg.role === 'assistant' && (
                    <div className="w-7 h-7 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-lg flex items-center justify-center shrink-0 mt-1">
                      <Brain className="w-4 h-4 text-white" />
                    </div>
                  )}
                  <div className={`max-w-[80%] rounded-xl p-4 ${msg.role === 'user' ? 'bg-purple-500/20 border border-purple-500/30 text-white' : 'bg-white/5 border border-white/10 text-gray-300'}`}>
                    {msg.role === 'user' ? <p className="text-sm">{msg.content}</p> : <div className="text-sm leading-relaxed">{formatText(msg.content)}</div>}
                  </div>
                  {msg.role === 'user' && <div className="w-7 h-7 bg-white/10 rounded-lg flex items-center justify-center shrink-0 mt-1"><User className="w-4 h-4 text-gray-400" /></div>}
                </div>
              ))}
              {chatLoading && (
                <div className="flex gap-3">
                  <div className="w-7 h-7 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-lg flex items-center justify-center shrink-0"><Brain className="w-4 h-4 text-white" /></div>
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4"><Loader2 className="w-4 h-4 text-purple-400 animate-spin" /></div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="border-t border-white/10 p-4">
              <div className="flex gap-3">
                <input type="text" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder="Ask about strategy, keywords, competitors..." disabled={chatLoading}
                  className="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 text-sm" />
                <button onClick={sendMessage} disabled={chatLoading || !input.trim()}
                  className="bg-gradient-to-r from-purple-500 to-cyan-500 text-white px-5 py-3 rounded-xl font-medium hover:shadow-lg transition-all disabled:opacity-50">
                  {chatLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
