// frontend/components/LocalSEOPanel.tsx — Local SEO / Google Business Profile
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { MapPin, Building2, Phone, Globe, Star, CheckCircle, AlertTriangle, Loader2, RefreshCw, FileCode, ExternalLink } from 'lucide-react';

interface LocalSEOData {
  has_data: boolean; completeness: number;
  business_name?: string; address?: string; city?: string;
  postcode?: string; country?: string; phone?: string;
  category?: string; gbp_url?: string; gbp_status?: string;
  review_count?: number; avg_rating?: number;
  recommendations?: Array<{ priority: string; message: string; action: string }>;
}

interface Props { websiteId: number; }

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

export default function LocalSEOPanel({ websiteId }: Props) {
  const [data, setData] = useState<LocalSEOData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [schema, setSchema] = useState<any>(null);
  const [form, setForm] = useState({
    business_name: '', address: '', city: '', postcode: '',
    country: 'GB', phone: '', category: '', gbp_url: '',
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/local-seo/${websiteId}/status`);
      if (res.ok) {
        const d = await res.json();
        setData(d);
        if (d.has_data) {
          setForm({
            business_name: d.business_name || '',
            address: d.address || '',
            city: d.city || '',
            postcode: d.postcode || '',
            country: d.country || 'GB',
            phone: d.phone || '',
            category: d.category || '',
            gbp_url: d.gbp_url || '',
          });
        }
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const saveData = async () => {
    setSaving(true);
    try {
      await fetch(`${API_URL}/api/local-seo/${websiteId}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, gbp_status: 'claimed' }),
      });
      await fetchData();
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const checkCitations = async () => {
    setChecking(true);
    try {
      await fetch(`${API_URL}/api/local-seo/${websiteId}/check-citations`, { method: 'POST' });
    } catch (e) { console.error(e); }
    setChecking(false);
  };

  const getSchema = async () => {
    try {
      const res = await fetch(`${API_URL}/api/local-seo/${websiteId}/schema`);
      if (res.ok) setSchema(await res.json());
    } catch (e) { console.error(e); }
  };

  useEffect(() => { fetchData(); }, [websiteId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">Local SEO</h2>
          <p className="text-[#52525b] text-sm mt-1">Google Business Profile & local citations</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={checkCitations} disabled={checking} className="px-3 py-2 rounded-xl border border-white/[0.06] text-[#52525b] text-sm hover:text-[#f5f5f7] transition-colors flex items-center gap-1.5">
            {checking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Check Citations
          </button>
          <button onClick={getSchema} className="px-3 py-2 rounded-xl border border-white/[0.06] text-[#52525b] text-sm hover:text-[#f5f5f7] transition-colors flex items-center gap-1.5">
            <FileCode className="w-3.5 h-3.5" /> Schema
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      ) : (
        <>
          {/* Completeness Score */}
          {data?.has_data && (
            <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-6">
              <div className="flex items-center gap-6">
                <div className="relative w-20 h-20">
                  <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                    <circle cx="40" cy="40" r="34" fill="none" stroke="#1a1a1e" strokeWidth="6" />
                    <circle cx="40" cy="40" r="34" fill="none" stroke={data.completeness >= 80 ? '#4ade80' : data.completeness >= 50 ? '#fbbf24' : '#f87171'} strokeWidth="6"
                      strokeDasharray={`${(data.completeness / 100) * 214} 214`} strokeLinecap="round" />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-xl font-bold ${data.completeness >= 80 ? 'text-[#4ade80]' : data.completeness >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]'}`}>{data.completeness}%</span>
                  </div>
                </div>
                <div>
                  <p className="text-[#f5f5f7] font-medium">Profile Completeness</p>
                  <p className="text-[#52525b] text-sm">{data.completeness === 100 ? 'All fields complete' : `${100 - data.completeness}% remaining`}</p>
                  {data.gbp_status && (
                    <p className="text-[#52525b] text-xs mt-1 capitalize">GBP Status: {data.gbp_status.replace('_', ' ')}</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Business Info Form */}
          <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-6 space-y-4">
            <h3 className="text-[#f5f5f7] text-sm font-medium">Business Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                { key: 'business_name', label: 'Business Name', icon: Building2 },
                { key: 'address', label: 'Street Address', icon: MapPin },
                { key: 'city', label: 'City', icon: Globe },
                { key: 'postcode', label: 'Postcode', icon: MapPin },
                { key: 'phone', label: 'Phone', icon: Phone },
                { key: 'category', label: 'Business Category', icon: Building2 },
              ].map(field => (
                <div key={field.key} className="space-y-1.5">
                  <label className="text-[#52525b] text-xs uppercase tracking-wider flex items-center gap-1.5">
                    <field.icon className="w-3 h-3" /> {field.label}
                  </label>
                  <input
                    type="text"
                    value={(form as any)[field.key]}
                    onChange={e => setForm({ ...form, [field.key]: e.target.value })}
                    className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
                  />
                </div>
              ))}
              <div className="space-y-1.5 md:col-span-2">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Google Business Profile URL</label>
                <input
                  type="text"
                  value={form.gbp_url}
                  onChange={e => setForm({ ...form, gbp_url: e.target.value })}
                  placeholder="https://business.google.com/..."
                  className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
                />
              </div>
            </div>
            <button onClick={saveData} disabled={saving} className="px-5 py-2.5 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2 disabled:opacity-50">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              {saving ? 'Saving...' : 'Save Business Info'}
            </button>
          </div>

          {/* Recommendations */}
          {data?.recommendations && data.recommendations.length > 0 && (
            <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-6 space-y-3">
              <h3 className="text-[#f5f5f7] text-sm font-medium flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#fbbf24]" /> Recommendations
              </h3>
              {data.recommendations.map((rec, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={`rounded-xl border p-4 ${rec.priority === 'high' ? 'border-[#f87171]/20 bg-[#f87171]/5' : 'border-[#fbbf24]/20 bg-[#fbbf24]/5'}`}
                >
                  <p className="text-[#f5f5f7] text-sm">{rec.message}</p>
                  <p className="text-[#7c6cf9] text-xs mt-1">{rec.action}</p>
                </motion.div>
              ))}
            </div>
          )}

          {/* Schema Output */}
          {schema && !schema.error && (
            <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
                <span className="text-[#f5f5f7] text-sm font-medium flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-[#7c6cf9]" /> LocalBusiness Schema
                </span>
              </div>
              <pre className="p-5 text-xs text-[#a1a1aa] font-mono overflow-x-auto whitespace-pre-wrap">
                {schema.json_ld}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
