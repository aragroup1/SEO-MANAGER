// frontend/components/SchemaGenerator.tsx — Schema.org JSON-LD Generator
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileCode, Copy, Check, Sparkles, AlertTriangle, CheckCircle, Loader2, ChevronDown } from 'lucide-react';

const SCHEMA_TYPES = [
  { id: 'Product', label: 'Product', icon: '🛍️', fields: ['name', 'description', 'brand', 'price', 'currency', 'sku', 'image', 'availability', 'rating', 'review_count'] },
  { id: 'Article', label: 'Article', icon: '📰', fields: ['headline', 'description', 'author', 'date_published', 'date_modified', 'image', 'publisher', 'publisher_logo'] },
  { id: 'Organization', label: 'Organization', icon: '🏢', fields: ['name', 'url', 'logo', 'description', 'phone', 'email', 'social_links'] },
  { id: 'LocalBusiness', label: 'LocalBusiness', icon: '📍', fields: ['name', 'description', 'url', 'phone', 'email', 'image', 'address', 'city', 'postcode', 'country', 'latitude', 'longitude', 'price_range'] },
  { id: 'FAQPage', label: 'FAQ Page', icon: '❓', fields: ['faqs'] },
  { id: 'WebSite', label: 'WebSite', icon: '🌐', fields: ['name', 'url', 'has_search'] },
  { id: 'BreadcrumbList', label: 'Breadcrumbs', icon: '🍞', fields: ['items'] },
];

interface Props { websiteId: number; }

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

export default function SchemaGenerator({ websiteId }: Props) {
  const [selectedType, setSelectedType] = useState('Product');
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showTypePicker, setShowTypePicker] = useState(false);

  const currentType = SCHEMA_TYPES.find(t => t.id === selectedType) || SCHEMA_TYPES[0];

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/schema/${websiteId}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schema_type: selectedType, data: formData }),
      });
      if (res.ok) setResult(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const copyToClipboard = () => {
    if (result?.json_ld) {
      navigator.clipboard.writeText(result.json_ld);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const renderField = (field: string) => {
    const value = formData[field] || '';
    if (field === 'social_links') {
      return (
        <textarea
          key={field}
          placeholder="One URL per line"
          value={Array.isArray(value) ? value.join('\n') : value}
          onChange={e => setFormData({ ...formData, [field]: e.target.value.split('\n').filter(Boolean) })}
          className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50 min-h-[80px] resize-y"
        />
      );
    }
    if (field === 'faqs') {
      return (
        <textarea
          key={field}
          placeholder={`JSON format: [{"question": "...", "answer": "..."}]`}
          value={typeof value === 'string' ? value : JSON.stringify(value || [], null, 2)}
          onChange={e => {
            try { setFormData({ ...formData, [field]: JSON.parse(e.target.value) }); }
            catch { setFormData({ ...formData, [field]: e.target.value }); }
          }}
          className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50 min-h-[120px] resize-y font-mono text-xs"
        />
      );
    }
    if (field === 'items') {
      return (
        <textarea
          key={field}
          placeholder={`JSON format: [{"name": "Home", "url": "/"}, {"name": "Products", "url": "/products"}]`}
          value={typeof value === 'string' ? value : JSON.stringify(value || [], null, 2)}
          onChange={e => {
            try { setFormData({ ...formData, [field]: JSON.parse(e.target.value) }); }
            catch { setFormData({ ...formData, [field]: e.target.value }); }
          }}
          className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50 min-h-[120px] resize-y font-mono text-xs"
        />
      );
    }
    if (field === 'has_search') {
      return (
        <select
          key={field}
          value={value ? 'true' : 'false'}
          onChange={e => setFormData({ ...formData, [field]: e.target.value === 'true' })}
          className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm focus:outline-none focus:border-[#7c6cf9]/50"
        >
          <option value="false">No</option>
          <option value="true">Yes</option>
        </select>
      );
    }
    return (
      <input
        key={field}
        type="text"
        placeholder={field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
        value={value}
        onChange={e => setFormData({ ...formData, [field]: e.target.value })}
        className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
      />
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[#f5f5f7]">Schema.org Generator</h2>
        <p className="text-[#52525b] text-sm mt-1">Generate structured data JSON-LD for rich snippets</p>
      </div>

      {/* Schema Type Selector */}
      <div className="relative">
        <button
          onClick={() => setShowTypePicker(!showTypePicker)}
          className="w-full flex items-center justify-between bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm hover:border-[#7c6cf9]/30 transition-colors"
        >
          <span className="flex items-center gap-2">
            <span className="text-lg">{currentType.icon}</span>
            {currentType.label}
          </span>
          <ChevronDown className={`w-4 h-4 text-[#52525b] transition-transform ${showTypePicker ? 'rotate-180' : ''}`} />
        </button>
        <AnimatePresence>
          {showTypePicker && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="absolute top-full left-0 right-0 mt-2 bg-[#0f0f12] border border-white/[0.06] rounded-xl overflow-hidden z-20"
            >
              {SCHEMA_TYPES.map(t => (
                <button
                  key={t.id}
                  onClick={() => { setSelectedType(t.id); setShowTypePicker(false); setResult(null); }}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-sm hover:bg-white/[0.04] transition-colors ${selectedType === t.id ? 'text-[#7c6cf9] bg-[#7c6cf9]/10' : 'text-[#f5f5f7]'}`}
                >
                  <span className="text-lg">{t.icon}</span>
                  {t.label}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Form Fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {currentType.fields.map(field => (
          <div key={field} className="space-y-1.5">
            <label className="text-[#52525b] text-xs uppercase tracking-wider">{field.replace(/_/g, ' ')}</label>
            {renderField(field)}
          </div>
        ))}
      </div>

      <button
        onClick={handleGenerate}
        disabled={loading}
        className="px-6 py-3 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2 disabled:opacity-50"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
        {loading ? 'Generating...' : 'Generate Schema'}
      </button>

      {/* Result */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Validation */}
            {result.validation && (
              <div className={`rounded-xl border p-4 ${result.validation.valid ? 'border-[#4ade80]/20 bg-[#4ade80]/5' : 'border-[#fbbf24]/20 bg-[#fbbf24]/5'}`}>
                <div className="flex items-center gap-2 mb-2">
                  {result.validation.valid ? <CheckCircle className="w-4 h-4 text-[#4ade80]" /> : <AlertTriangle className="w-4 h-4 text-[#fbbf24]" />}
                  <span className={`text-sm font-medium ${result.validation.valid ? 'text-[#4ade80]' : 'text-[#fbbf24]'}`}>
                    {result.validation.valid ? 'Valid Schema' : 'Validation Issues'}
                  </span>
                </div>
                {result.validation.errors?.length > 0 && (
                  <div className="space-y-1 mt-2">
                    {result.validation.errors.map((e: string, i: number) => (
                      <p key={i} className="text-[#f87171] text-xs">• {e}</p>
                    ))}
                  </div>
                )}
                {result.validation.warnings?.length > 0 && (
                  <div className="space-y-1 mt-2">
                    {result.validation.warnings.map((w: string, i: number) => (
                      <p key={i} className="text-[#fbbf24] text-xs">• {w}</p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* JSON-LD Output */}
            <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
                <div className="flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-[#7c6cf9]" />
                  <span className="text-[#f5f5f7] text-sm font-medium">JSON-LD Output</span>
                </div>
                <button onClick={copyToClipboard} className="flex items-center gap-1.5 text-[#7c6cf9] text-xs hover:text-[#9b8ffb] transition-colors">
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre className="p-5 text-xs text-[#a1a1aa] font-mono overflow-x-auto whitespace-pre-wrap">
                {result.json_ld}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
