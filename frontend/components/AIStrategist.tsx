// frontend/components/AIStrategist.tsx
'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Send, Loader2, User, Bot, Sparkles,
  AlertTriangle, TrendingUp, Target, FileText, X,
  MessageSquare, Lightbulb, ChevronDown
} from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export default function AIStrategist({ websiteId }: { websiteId: number }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  // Reset on website change
  useEffect(() => {
    setMessages([]);
    setInput('');
    setError('');
  }, [websiteId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    const msg = input.trim();
    if (!msg || loading) return;

    const userMessage: Message = { role: 'user', content: msg, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setError('');

    try {
      const r = await fetch(`${API_URL}/api/strategist/${websiteId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          history: messages.map(m => ({ role: m.role, content: m.content }))
        })
      });

      if (r.ok) {
        const data = await r.json();
        if (data.error) {
          setError(data.error);
        } else {
          const assistantMessage: Message = {
            role: 'assistant',
            content: data.response,
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, assistantMessage]);
        }
      } else {
        setError('Failed to get response');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const quickPrompts = [
    { icon: TrendingUp, label: 'What should I focus on first?', prompt: 'Based on my current SEO data, what are the top 3 things I should focus on right now to get the biggest improvement in rankings?' },
    { icon: Target, label: 'Keyword opportunities', prompt: 'Looking at my current keyword rankings, what are my biggest keyword opportunities? Which keywords am I close to page 1 for?' },
    { icon: AlertTriangle, label: 'Critical issues', prompt: 'What are the most critical SEO issues on my site right now and how do I fix them?' },
    { icon: FileText, label: 'Content strategy', prompt: 'Based on my current rankings and tracked keywords, what content should I create next? Give me a specific content plan.' },
    { icon: Sparkles, label: 'AI search readiness', prompt: 'How well optimized is my site for AI search engines like ChatGPT and Perplexity? What should I do to appear in AI-generated answers?' },
    { icon: Lightbulb, label: 'Quick wins', prompt: 'What are the quickest SEO wins I can implement today that will have an impact within the next 2 weeks?' },
  ];

  // Format AI response with basic markdown
  const formatResponse = (text: string) => {
    return text.split('\n').map((line, i) => {
      // Bold
      line = line.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>');
      // Bullet points
      if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        return <p key={i} className="ml-4 mb-1" dangerouslySetInnerHTML={{ __html: '• ' + line.trim().substring(2) }} />;
      }
      // Numbered lists
      const numMatch = line.trim().match(/^(\d+)\.\s(.*)/);
      if (numMatch) {
        return <p key={i} className="ml-4 mb-1" dangerouslySetInnerHTML={{ __html: `<span class="text-purple-400 font-bold">${numMatch[1]}.</span> ${numMatch[2]}` }} />;
      }
      // Empty lines
      if (!line.trim()) return <br key={i} />;
      // Regular text
      return <p key={i} className="mb-1" dangerouslySetInnerHTML={{ __html: line }} />;
    });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-lg flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            AI SEO Strategist
          </h2>
          <p className="text-purple-300 mt-1 text-sm">Ask anything about your website's SEO — powered by your real data</p>
        </div>
      </div>

      {/* Chat Container */}
      <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 overflow-hidden" style={{ height: 'calc(100vh - 200px)', minHeight: '500px' }}>
        <div className="flex flex-col h-full">

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center py-8">
                <div className="w-16 h-16 bg-gradient-to-br from-purple-500/20 to-cyan-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Brain className="w-8 h-8 text-purple-400" />
                </div>
                <h3 className="text-white font-semibold mb-2">Your AI SEO Strategist</h3>
                <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                  I have full access to your website's audit data, keyword rankings, tracked keywords, and fix history. Ask me anything.
                </p>

                {/* Quick Prompts */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-lg mx-auto">
                  {quickPrompts.map((qp, i) => (
                    <button key={i} onClick={() => { setInput(qp.prompt); }}
                      className="flex items-center gap-2 text-left p-3 bg-white/5 hover:bg-white/10 rounded-lg border border-white/10 hover:border-purple-500/30 transition-all">
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
                <div className={`max-w-[80%] rounded-xl p-4 ${
                  msg.role === 'user'
                    ? 'bg-purple-500/20 border border-purple-500/30 text-white'
                    : 'bg-white/5 border border-white/10 text-gray-300'
                }`}>
                  {msg.role === 'user' ? (
                    <p className="text-sm">{msg.content}</p>
                  ) : (
                    <div className="text-sm leading-relaxed">{formatResponse(msg.content)}</div>
                  )}
                  <p className="text-[10px] text-gray-600 mt-2">{new Date(msg.timestamp).toLocaleTimeString()}</p>
                </div>
                {msg.role === 'user' && (
                  <div className="w-7 h-7 bg-white/10 rounded-lg flex items-center justify-center shrink-0 mt-1">
                    <User className="w-4 h-4 text-gray-400" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-3">
                <div className="w-7 h-7 bg-gradient-to-br from-purple-500 to-cyan-500 rounded-lg flex items-center justify-center shrink-0 mt-1">
                  <Brain className="w-4 h-4 text-white" />
                </div>
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                    <span className="text-gray-400 text-sm">Analyzing your data...</span>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t border-white/10 p-4">
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Ask about your SEO strategy, keywords, competitors..."
                className="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 text-sm"
                disabled={loading}
              />
              <button onClick={sendMessage} disabled={loading || !input.trim()}
                className="bg-gradient-to-r from-purple-500 to-cyan-500 text-white px-5 py-3 rounded-xl font-medium hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-gray-600 text-[10px] mt-2 text-center">
              Powered by your real SEO data · Audit scores, keyword rankings, tracked keywords, and fix history
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
