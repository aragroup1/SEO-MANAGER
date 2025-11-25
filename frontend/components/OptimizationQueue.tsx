// frontend/components/OptimizationQueue.tsx
'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Eye, Sparkles } from 'lucide-react';

export default function OptimizationQueue({ websiteId }: { websiteId: number }) {
  const [optimizations, setOptimizations] = useState([]);

  return (
    <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
      <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-yellow-400" />
        Pending Optimizations
      </h3>
      <p className="text-purple-300">No pending optimizations at the moment.</p>
    </div>
  );
}
