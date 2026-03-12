import { useState, useEffect } from 'react';
import { getProjectStorage, getCleanableFiles, cleanupProject } from '../api/client';

export default function StoragePanel({ projectName }) {
  const [storage, setStorage] = useState(null);
  const [cleanable, setCleanable] = useState([]);
  const [cleaning, setCleaning] = useState(false);
  const [result, setResult] = useState(null);

  const load = async () => {
    try {
      const [s, c] = await Promise.all([
        getProjectStorage(projectName),
        getCleanableFiles(projectName),
      ]);
      setStorage(s);
      setCleanable(c);
    } catch (e) {
      // Not critical
    }
  };

  useEffect(() => { load(); }, [projectName]);

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      const r = await cleanupProject(projectName);
      setResult(r);
      await load();
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setCleaning(false);
    }
  };

  if (!storage) return null;

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-gray-300">Disk Usage</h4>

      {/* Total */}
      <div className="flex items-center justify-between bg-[#1a1f2e] rounded px-3 py-2">
        <span className="text-sm text-gray-400">Total</span>
        <span className="text-sm font-mono text-gray-200">{storage.total_human}</span>
      </div>

      {/* Breakdown */}
      {Object.entries(storage.breakdown).length > 0 && (
        <div className="space-y-1">
          {Object.entries(storage.breakdown).map(([dir, info]) => (
            <div key={dir} className="flex items-center justify-between px-3 py-1">
              <span className="text-xs text-gray-500">{dir}/</span>
              <span className="text-xs font-mono text-gray-400">{info.human}</span>
            </div>
          ))}
        </div>
      )}

      {/* Cleanable files */}
      {cleanable.length > 0 && (
        <div className="border border-yellow-800/40 bg-yellow-900/10 rounded p-3 space-y-2">
          <p className="text-xs text-yellow-400">
            {cleanable.length} intermediate file{cleanable.length > 1 ? 's' : ''} can be removed:
          </p>
          {cleanable.map((f, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <div>
                <span className="text-gray-300 font-mono">{f.path}</span>
                <span className="text-gray-600 ml-2">({f.size_human})</span>
              </div>
            </div>
          ))}
          <button
            onClick={handleCleanup}
            disabled={cleaning}
            className="text-xs bg-yellow-700/30 text-yellow-300 px-3 py-1.5 rounded hover:bg-yellow-700/50 disabled:opacity-50"
          >
            {cleaning ? 'Cleaning...' : 'Clean Up'}
          </button>
        </div>
      )}

      {/* Result */}
      {result && !result.error && (
        <p className="text-xs text-green-400">
          Removed {result.cleaned} file{result.cleaned !== 1 ? 's' : ''}, freed {result.freed_human}
        </p>
      )}
      {result?.error && (
        <p className="text-xs text-red-400">{result.error}</p>
      )}
    </div>
  );
}
