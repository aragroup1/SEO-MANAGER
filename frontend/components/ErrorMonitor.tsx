// frontend/components/ErrorMonitor.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, CheckCircle, XCircle, Zap, Clock } from 'lucide-react';

export default function ErrorMonitor({ websiteId }: { websiteId: number }) {
  const [errors, setErrors] = useState([]);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchErrors();
  }, [websiteId]);

  const fetchErrors = async () => {
    const response = await fetch(`/api/errors/${websiteId}`);
    const data = await response.json();
    setErrors(data);
  };

  const fixError = async (errorId: number) => {
    await fetch(`/api/errors/${errorId}/fix`, { method: 'POST' });
    fetchErrors();
  };

  return (
    <div className="space-y-6">
      <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
        <h3 className="text-xl font-bold text-white mb-4">Error Monitor</h3>
        
        <div className="space-y-4">
          {errors.map((error: any) => (
            <div key={error.id} className="bg-white/5 rounded-xl p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-white font-medium flex items-center gap-2">
                    <AlertTriangle className={`w-4 h-4 ${
                      error.severity === 'critical' ? 'text-red-400' :
                      error.severity === 'high' ? 'text-orange-400' :
                      error.severity === 'medium' ? 'text-yellow-400' :
                      'text-blue-400'
                    }`} />
                    {error.title}
                  </h4>
                  <p className="text-purple-300 text-sm mt-1">{error.description}</p>
                  <div className="flex items-center gap-4 mt-2">
                    <span className="text-xs text-gray-400">
                      Affects {error.affected_urls?.length || 0} pages
                    </span>
                    {error.auto_fixed ? (
                      <span className="text-xs text-green-400 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" />
                        Auto-fixed
                      </span>
                    ) : (
                      <button
                        onClick={() => fixError(error.id)}
                        className="text-xs bg-purple-500/20 text-purple-400 px-2 py-1 rounded flex items-center gap-1 hover:bg-purple-500/30"
                      >
                        <Zap className="w-3 h-3" />
                        Auto-fix
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
