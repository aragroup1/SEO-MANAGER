// frontend/components/CompetitorAnalysis.tsx
'use client';

import { useState, useEffect } from 'react';
import { Users, TrendingUp, Link, Target } from 'lucide-react';

export default function CompetitorAnalysis({ websiteId }: { websiteId: number }) {
  const [competitors, setCompetitors] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);

  const analyzeCompetitors = async () => {
    setAnalyzing(true);
    await fetch(`/api/competitors/${websiteId}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        competitor_domains: ['competitor1.com', 'competitor2.com']
      })
    });
    setAnalyzing(false);
  };

  return (
    <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-white flex items-center gap-2">
          <Users className="w-5 h-5 text-purple-400" />
          Competitor Analysis
        </h3>
        <button
          onClick={analyzeCompetitors}
          disabled={analyzing}
          className="bg-purple-500 text-white px-4 py-2 rounded-lg font-medium hover:bg-purple-600 transition-all disabled:opacity-50"
        >
          {analyzing ? 'Analyzing...' : 'Analyze Competitors'}
        </button>
      </div>

      <div className="space-y-4">
        {competitors.map((competitor: any) => (
          <div key={competitor.id} className="bg-white/5 rounded-xl p-4">
            <h4 className="text-white font-medium mb-2">{competitor.competitor_domain}</h4>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-gray-400">Traffic</p>
                <p className="text-white font-bold">{competitor.traffic_estimate?.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-gray-400">Keywords</p>
                <p className="text-white font-bold">{competitor.keyword_overlap?.length || 0}</p>
              </div>
              <div>
                <p className="text-gray-400">Backlinks</p>
                <p className="text-white font-bold">{competitor.backlink_gaps?.total_backlinks || 0}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
