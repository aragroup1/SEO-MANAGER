// frontend/components/ContentWriter.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText, Plus, Loader2, Sparkles, Lightbulb, Trash2,
  ChevronRight, ExternalLink, Copy, CheckCircle, Star,
  BookOpen, ShoppingCart, Layout, HelpCircle, Wrench,
  Target, TrendingUp, X, Eye
} from 'lucide-react';

interface ContentIdea {
  title: string; content_type: string; target_keyword: string;
  estimated_volume: string; difficulty: string; why: string;
  supports_keywords?: string[];
}

interface ContentPiece {
  id: number; title: string; content_type: string; status: string;
  keywords: string[]; has_content: boolean; created_at: string | null;
}

export default function ContentWriter({ websiteId }: { websiteId: number }) {
  const [activeTab, setActiveTab] = useState<'create' | 'ideas' | 'library'>('create');
  const [generating, setGenerating] = useState(false);
  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [loadingIdeas, setLoadingIdeas] = useState(false);
  const [library, setLibrary] = useState<ContentPiece[]>([]);
  const [loadingLibrary, setLoadingLibrary] = useState(false);
  const [generatedContent, setGeneratedContent] = useState<any>(null);
  const [viewingContent, setViewingContent] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  // Form state
  const [topic, setTopic] = useState('');
  const [contentType, setContentType] = useState('blog_post');
  const [keywords, setKeywords] = useState('');
  const [wordCount, setWordCount] = useState(800);
  const [tone, setTone] = useState('professional');
  const [instructions, setInstructions] = useState('');

  const API = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => { fetchLibrary(); }, [websiteId]);

  const fetchLibrary = async () => {
    setLoadingLibrary(true);
    try {
      const r = await fetch(`${API}/api/content/${websiteId}/list`);
      if (r.ok) { const d = await r.json(); setLibrary(d.content || []); }
    } catch {} finally { setLoadingLibrary(false); }
  };

  const generateContent = async () => {
    if (!topic.trim()) return;
    setGenerating(true); setGeneratedContent(null);
    try {
      const r = await fetch(`${API}/api/content/${websiteId}/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic, content_type: contentType,
          target_keywords: keywords.split(',').map(k => k.trim()).filter(Boolean),
          word_count: wordCount, tone, instructions,
        })
      });
      if (r.ok) {
        const d = await r.json();
        if (d.error) { alert(d.error); }
        else { setGeneratedContent(d); fetchLibrary(); }
      }
    } catch { alert('Failed to generate'); }
    finally { setGenerating(false); }
  };

  const fetchIdeas = async () => {
    setLoadingIdeas(true); setIdeas([]);
    try {
      const r = await fetch(`${API}/api/content/${websiteId}/ideas`, { method: 'POST' });
      if (r.ok) { const d = await r.json(); setIdeas(d.ideas || []); }
    } catch {} finally { setLoadingIdeas(false); }
  };

  const viewContent = async (id: number) => {
    try {
      const r = await fetch(`${API}/api/content/${websiteId}/${id}`);
      if (r.ok) { const d = await r.json(); setViewingContent(d); }
    } catch {}
  };

  const deleteContent = async (id: number) => {
    if (!confirm('Delete this content?')) return;
    try {
      await fetch(`${API}/api/content/${websiteId}/${id}`, { method: 'DELETE' });
      setLibrary(prev => prev.filter(c => c.id !== id));
      if (viewingContent?.id === id) setViewingContent(null);
    } catch {}
  };

  const copyHtml = (html: string) => {
    navigator.clipboard.writeText(html);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  const typeIcons: Record<string, any> = {
    blog_post: BookOpen, product_description: ShoppingCart,
    landing_page: Layout, faq_page: HelpCircle, how_to_guide: Wrench,
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <FileText className="w-6 h-6 text-purple-400" /> Content Writer
          </h2>
          <p className="text-gray-400 mt-1 text-sm">AI-generated SEO content — blog posts, descriptions, landing pages</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {[
          { id: 'create' as const, label: 'Create Content', icon: Plus },
          { id: 'ideas' as const, label: 'Content Ideas', icon: Lightbulb },
          { id: 'library' as const, label: `Library (${library.length})`, icon: BookOpen },
        ].map(t => (
          <button key={t.id} onClick={() => { setActiveTab(t.id); if (t.id === 'ideas' && !ideas.length) fetchIdeas(); if (t.id === 'library') fetchLibrary(); }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === t.id ? 'bg-purple-500/30 text-white border border-purple-500/50' : 'bg-white/5 text-gray-400 hover:bg-white/10 border border-transparent'
            }`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* ═══ CREATE ═══ */}
      {activeTab === 'create' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Form */}
          <div className="bg-white/5 rounded-xl p-5 border border-white/10 space-y-4">
            <div>
              <label className="block text-gray-400 text-xs mb-1">Content Type</label>
              <select value={contentType} onChange={e => setContentType(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white text-sm">
                <option value="blog_post">Blog Post</option>
                <option value="product_description">Product Description</option>
                <option value="landing_page">Landing Page</option>
                <option value="faq_page">FAQ Page</option>
                <option value="how_to_guide">How-To Guide</option>
              </select>
            </div>

            <div>
              <label className="block text-gray-400 text-xs mb-1">Topic / Title</label>
              <input type="text" value={topic} onChange={e => setTopic(e.target.value)}
                placeholder="e.g. How to Choose the Right Barcode for Your Product"
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500" />
            </div>

            <div>
              <label className="block text-gray-400 text-xs mb-1">Target Keywords (comma-separated)</label>
              <input type="text" value={keywords} onChange={e => setKeywords(e.target.value)}
                placeholder="e.g. barcode types, product barcodes, EAN barcode"
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-gray-400 text-xs mb-1">Word Count</label>
                <select value={wordCount} onChange={e => setWordCount(Number(e.target.value))}
                  className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white text-sm">
                  <option value={500}>500 words</option>
                  <option value={800}>800 words</option>
                  <option value={1200}>1,200 words</option>
                  <option value={2000}>2,000 words</option>
                </select>
              </div>
              <div>
                <label className="block text-gray-400 text-xs mb-1">Tone</label>
                <select value={tone} onChange={e => setTone(e.target.value)}
                  className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white text-sm">
                  <option value="professional">Professional</option>
                  <option value="casual">Casual</option>
                  <option value="authoritative">Authoritative</option>
                  <option value="friendly">Friendly</option>
                  <option value="technical">Technical</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-gray-400 text-xs mb-1">Additional Instructions (optional)</label>
              <textarea value={instructions} onChange={e => setInstructions(e.target.value)}
                placeholder="Any specific points to include, competitors to reference, etc."
                className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500 h-20 resize-none" />
            </div>

            <button onClick={generateContent} disabled={generating || !topic.trim()}
              className="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white py-3 rounded-lg font-medium hover:shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50">
              {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating ({contentType === 'blog_post' ? '30-60s' : '15-30s'})...</> : <><Sparkles className="w-4 h-4" /> Generate Content</>}
            </button>
          </div>

          {/* Preview */}
          <div className="bg-white/5 rounded-xl p-5 border border-white/10">
            {!generatedContent && !generating && (
              <div className="text-center py-12">
                <FileText className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                <p className="text-gray-500 text-sm">Generated content will appear here</p>
              </div>
            )}

            {generating && (
              <div className="text-center py-12">
                <Loader2 className="w-10 h-10 text-purple-400 animate-spin mx-auto mb-4" />
                <p className="text-white font-medium">Writing your content...</p>
                <p className="text-gray-500 text-xs mt-1">AI is researching keywords and writing SEO-optimized content</p>
              </div>
            )}

            {generatedContent?.content && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-white font-semibold text-sm">{generatedContent.content.title || 'Generated Content'}</h3>
                  <button onClick={() => copyHtml(generatedContent.content.content_html || '')}
                    className="text-xs bg-white/10 text-gray-300 px-3 py-1.5 rounded-lg hover:bg-white/20 flex items-center gap-1">
                    {copied ? <CheckCircle className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied!' : 'Copy HTML'}
                  </button>
                </div>

                {generatedContent.content.meta_title && (
                  <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
                    <p className="text-green-400 text-[10px] font-medium">META TITLE</p>
                    <p className="text-white text-sm">{generatedContent.content.meta_title}</p>
                    <p className="text-green-400 text-[10px] font-medium mt-2">META DESCRIPTION</p>
                    <p className="text-white text-sm">{generatedContent.content.meta_description}</p>
                  </div>
                )}

                <div className="bg-white rounded-lg p-4 max-h-[500px] overflow-y-auto">
                  <div className="prose prose-sm max-w-none text-gray-800"
                    dangerouslySetInnerHTML={{ __html: generatedContent.content.content_html || '' }} />
                </div>

                {generatedContent.content.faq?.length > 0 && (
                  <div className="bg-purple-500/10 rounded-lg p-3 border border-purple-500/20">
                    <p className="text-purple-400 text-xs font-medium mb-2">FAQ (for Schema markup)</p>
                    {generatedContent.content.faq.map((f: any, i: number) => (
                      <div key={i} className="mb-2">
                        <p className="text-white text-sm font-medium">{f.question}</p>
                        <p className="text-gray-400 text-xs">{f.answer}</p>
                      </div>
                    ))}
                  </div>
                )}

                {generatedContent.content.internal_link_suggestions?.length > 0 && (
                  <div className="bg-blue-500/10 rounded-lg p-3 border border-blue-500/20">
                    <p className="text-blue-400 text-xs font-medium mb-2">INTERNAL LINK SUGGESTIONS</p>
                    {generatedContent.content.internal_link_suggestions.map((l: any, i: number) => (
                      <p key={i} className="text-gray-300 text-xs mb-1">
                        Link "{l.anchor_text}" → {l.suggested_page} <span className="text-gray-600">({l.reason})</span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══ IDEAS ═══ */}
      {activeTab === 'ideas' && (
        <div className="space-y-4">
          {!ideas.length && !loadingIdeas && (
            <div className="bg-white/5 rounded-xl p-10 border border-white/10 text-center">
              <Lightbulb className="w-14 h-14 text-yellow-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Get Content Ideas</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">AI analyzes your keyword data and suggests content that would boost your rankings.</p>
              <button onClick={fetchIdeas}
                className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Generate Ideas
              </button>
            </div>
          )}

          {loadingIdeas && (
            <div className="bg-yellow-500/10 rounded-xl p-8 text-center border border-yellow-500/20">
              <Loader2 className="w-10 h-10 text-yellow-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Analyzing keyword gaps and generating ideas...</p>
            </div>
          )}

          {ideas.length > 0 && (
            <div className="space-y-3">
              {ideas.map((idea, i) => {
                const Icon = typeIcons[idea.content_type] || FileText;
                return (
                  <div key={i} className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-purple-500/30 transition-all">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <div className="p-2 bg-purple-500/20 rounded-lg shrink-0"><Icon className="w-4 h-4 text-purple-400" /></div>
                        <div className="flex-1 min-w-0">
                          <h4 className="text-white font-medium text-sm">{idea.title}</h4>
                          <p className="text-gray-500 text-xs mt-0.5">{idea.why}</p>
                          <div className="flex items-center gap-3 mt-2 flex-wrap">
                            <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded">{idea.target_keyword}</span>
                            <span className="text-xs text-gray-500">Vol: {idea.estimated_volume}</span>
                            <span className="text-xs text-gray-500">Diff: {idea.difficulty}</span>
                            {(idea as any).road_to_one_connection && (
                              <span className="text-xs bg-green-500/10 text-green-400 px-2 py-0.5 rounded flex items-center gap-1">
                                <Target className="w-3 h-3" /> R2#1: {(idea as any).road_to_one_connection}
                              </span>
                            )}
                          </div>
                          {idea.supports_keywords && idea.supports_keywords.length > 0 && (
                            <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                              <span className="text-[10px] text-gray-600">Supports:</span>
                              {idea.supports_keywords.slice(0, 3).map((sk, j) => (
                                <span key={j} className="text-[10px] bg-purple-500/10 text-purple-400 px-1.5 py-0.5 rounded">{sk}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                      <button onClick={() => { setTopic(idea.title); setContentType(idea.content_type); setKeywords(idea.target_keyword); setActiveTab('create'); }}
                        className="bg-purple-500/20 text-purple-400 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-purple-500/30 flex items-center gap-1 shrink-0 ml-3">
                        <Plus className="w-3 h-3" /> Write This
                      </button>
                    </div>
                  </div>
                );
              })}
              <button onClick={fetchIdeas} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 flex items-center justify-center gap-2">
                <Lightbulb className="w-4 h-4" /> Regenerate Ideas
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ LIBRARY ═══ */}
      {activeTab === 'library' && (
        <div className="space-y-3">
          {library.length === 0 && (
            <div className="bg-white/5 rounded-xl p-10 border border-white/10 text-center">
              <BookOpen className="w-14 h-14 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No content generated yet. Go to "Create Content" to get started.</p>
            </div>
          )}

          {library.map(item => {
            const Icon = typeIcons[item.content_type?.toLowerCase().replace(/ /g, '_')] || FileText;
            return (
              <div key={item.id} className="bg-white/5 rounded-xl p-4 border border-white/10 flex items-center justify-between hover:bg-white/8 transition-all">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="p-2 bg-white/10 rounded-lg shrink-0"><Icon className="w-4 h-4 text-purple-400" /></div>
                  <div className="min-w-0">
                    <p className="text-white text-sm font-medium truncate">{item.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-500">{item.content_type}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${item.status === 'Published' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{item.status}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-3">
                  <button onClick={() => viewContent(item.id)} className="bg-white/10 text-gray-300 px-3 py-1.5 rounded-lg text-xs hover:bg-white/20 flex items-center gap-1">
                    <Eye className="w-3 h-3" /> View
                  </button>
                  <button onClick={() => deleteContent(item.id)} className="text-gray-600 hover:text-red-400 p-1.5"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Content Viewer Modal */}
      <AnimatePresence>
        {viewingContent && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-end" onClick={() => setViewingContent(null)}>
            <motion.div initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 25 }}
              className="w-full max-w-2xl bg-gray-900 border-l border-white/10 h-full overflow-y-auto" onClick={e => e.stopPropagation()}>
              <div className="p-6 space-y-4">
                <div className="flex items-start justify-between">
                  <h3 className="text-xl font-bold text-white">{viewingContent.title}</h3>
                  <button onClick={() => setViewingContent(null)} className="text-gray-400 hover:text-white p-1"><X className="w-5 h-5" /></button>
                </div>

                {viewingContent.content?.meta_title && (
                  <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20 text-sm">
                    <p className="text-green-400 text-[10px] font-medium">META TITLE: <span className="text-white">{viewingContent.content.meta_title}</span></p>
                    <p className="text-green-400 text-[10px] font-medium mt-1">META DESC: <span className="text-white">{viewingContent.content.meta_description}</span></p>
                  </div>
                )}

                <div className="flex gap-2">
                  <button onClick={() => copyHtml(viewingContent.content?.content_html || '')}
                    className="bg-purple-500/20 text-purple-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2 hover:bg-purple-500/30">
                    <Copy className="w-4 h-4" /> {copied ? 'Copied!' : 'Copy HTML'}
                  </button>
                </div>

                <div className="bg-white rounded-lg p-5 max-h-[60vh] overflow-y-auto">
                  <div className="prose prose-sm max-w-none text-gray-800"
                    dangerouslySetInnerHTML={{ __html: viewingContent.content?.content_html || 'No content' }} />
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
