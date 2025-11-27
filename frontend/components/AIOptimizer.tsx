// frontend/components/AIOptimizer.tsx
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Brain, Sparkles, Target, TrendingUp, Loader2 } from 'lucide-react';

export default function AIOptimizer({ websiteId }: { websiteId: number }) {
  const [keywords, setKeywords] = useState('');
  const [clusters, setClusters] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('cluster');

  const clusterKeywords = async () => {
    setLoading(true);
    const keywordList = keywords.split('\n').filter(k => k.trim());
    
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/keywords/cluster`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: keywordList })
      });
      
      const data = await response.json();
      setClusters(data);
    } catch (error) {
      console.error('Error clustering keywords:', error);
    } finally {
      setLoading(false);
    }
  };

  const analyzeGEO = async (url: string, query: string) => {
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/geo/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, target_query: query })
      });
      
      const data = await response.json();
      console.log('GEO Analysis:', data);
    } catch (error) {
      console.error('Error analyzing GEO:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
          <Brain className="w-5 h-5 text-purple-400" />
          AI-Powered Optimization
        </h3>

        <div className="flex gap-2 mb-4">
          {['cluster', 'intent', 'geo'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                activeTab === tab
                  ? 'bg-purple-500 text-white'
                  : 'bg-white/10 text-purple-300'
              }`}
            >
              {tab === 'cluster' ? 'Keyword Clustering' : 
               tab === 'intent' ? 'Intent Analysis' : 
               'AI Search Optimization'}
            </button>
          ))}
        </div>

        {activeTab === 'cluster' && (
          <div className="space-y-4">
            <textarea
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Enter keywords (one per line)"
              className="w-full h-32 bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-gray-400"
            />
            
            <button
              onClick={clusterKeywords}
              disabled={loading || !keywords}
              className="bg-purple-500 text-white px-4 py-2 rounded-lg font-medium hover:bg-purple-600 transition-all disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Cluster Keywords
            </button>

            {clusters && (
              <div className="space-y-3">
                {Object.entries(clusters.clusters).map(([clusterId, clusterKeywords]: any) => (
                  <div key={clusterId} className="bg-white/5 rounded-lg p-3">
                    <h4 className="text-purple-400 font-medium mb-2">
                      Cluster {parseInt(clusterId) + 1}: {clusters.representatives[clusterId]}
                    </h4>
                    <p className="text-white text-sm">
                      {clusterKeywords.join(', ')}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
