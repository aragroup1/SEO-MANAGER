// frontend/components/ContentCalendar.tsx
'use client';

import { useState, useEffect } from 'react';
import { Calendar, Plus, FileText, TrendingUp } from 'lucide-react';

export default function ContentCalendar({ websiteId }: { websiteId: number }) {
  const [content, setContent] = useState([]);

  useEffect(() => {
    fetchContent();
  }, [websiteId]);

  const fetchContent = async () => {
    const response = await fetch(`/api/content-calendar/${websiteId}`);
    const data = await response.json();
    setContent(data);
  };

  const generateCalendar = async () => {
    await fetch(`/api/content-calendar/${websiteId}/generate`, { method: 'POST' });
    fetchContent();
  };

  return (
    <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-white flex items-center gap-2">
          <Calendar className="w-5 h-5 text-purple-400" />
          Content Calendar
        </h3>
        <button
          onClick={generateCalendar}
          className="bg-purple-500 text-white px-4 py-2 rounded-lg font-medium hover:bg-purple-600 transition-all flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Generate Content
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {content.map((item: any) => (
          <div key={item.id} className="bg-white/5 rounded-xl p-4">
            <div className="flex items-start justify-between mb-2">
              <FileText className="w-5 h-5 text-purple-400" />
              <span className="text-xs text-gray-400">
                {new Date(item.publish_date).toLocaleDateString()}
              </span>
            </div>
            <h4 className="text-white font-medium mb-2">{item.title}</h4>
            <p className="text-purple-300 text-sm mb-3">{item.ai_generated_content?.substring(0, 100)}...</p>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">{item.content_type}</span>
              <div className="flex items-center gap-1 text-green-400 text-xs">
                <TrendingUp className="w-3 h-3" />
                +{item.estimated_traffic}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
