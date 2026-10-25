import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, History, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronRight } from 'lucide-react';
import ReactDiffViewer from 'react-diff-viewer-continued';

const API_BASE = import.meta.env.VITE_API_URL || '';

export default function ReplayComparison({ jobId }) {
  const [useCached, setUseCached] = useState(false);
  const [expandedDiffs, setExpandedDiffs] = useState(new Set());
  const queryClient = useQueryClient();

  // Fetch replay history
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['replay-history', jobId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/reliability/replay/${jobId}/history`);
      if (!response.ok) throw new Error('Failed to fetch replay history');
      return response.json();
    },
    enabled: !!jobId
  });

  // Replay execution mutation
  const replayMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(
        `${API_BASE}/api/reliability/replay/${jobId}?use_cached=${useCached}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('Replay failed');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['replay-history', jobId]);
    }
  });

  const handleReplay = () => {
    replayMutation.mutate();
  };

  const toggleDiff = (key) => {
    setExpandedDiffs((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  if (!jobId) {
    return null;
  }

  // Don't render empty panel when there's no replay history
  if (!historyLoading && !history?.history?.length && !replayMutation.data) {
    return null;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with Controls */}
      <div className="border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Play className="w-5 h-5" />
          Execution Replay
        </h2>

        {/* Replay Controls */}
        <div className="flex items-center gap-4 mb-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useCached}
              onChange={(e) => setUseCached(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">Use cached responses</span>
          </label>

          <button
            onClick={handleReplay}
            disabled={replayMutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Play className="w-4 h-4" />
            {replayMutation.isPending ? 'Replaying...' : 'Replay Execution'}
          </button>
        </div>

        {/* Latest Result Summary */}
        {replayMutation.data && (
          <ReplaySummary result={replayMutation.data} />
        )}
      </div>

      {/* Comparison View */}
      <div className="flex-1 overflow-y-auto">
        {replayMutation.data && (
          <ComparisonDetails
            comparison={replayMutation.data.comparison}
            expandedDiffs={expandedDiffs}
            toggleDiff={toggleDiff}
          />
        )}

        {/* History Section */}
        <div className="border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4">
          <h3 className="text-md font-semibold mb-3 flex items-center gap-2">
            <History className="w-4 h-4" />
            Replay History
          </h3>

          {historyLoading ? (
            <div className="text-center py-4 text-gray-500">Loading history...</div>
          ) : !history?.history?.length ? (
            <div className="text-center py-4 text-gray-500">No replay history</div>
          ) : (
            <div className="space-y-2">
              {history.history.map((item, idx) => (
                <HistoryCard key={idx} item={item} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ReplaySummary({ result }) {
  const { comparison } = result;
  const identicalCount = comparison.differences.filter((d) => d.identical).length;
  const differenceCount = comparison.differences.length - identicalCount;

  return (
    <div className="grid grid-cols-4 gap-4">
      <div className="bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
        <div className="text-sm text-gray-600 dark:text-gray-400">Original Status</div>
        <div className={`text-lg font-bold ${getStatusColor(comparison.original_status)}`}>
          {comparison.original_status}
        </div>
      </div>
      <div className="bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
        <div className="text-sm text-gray-600 dark:text-gray-400">Replay Status</div>
        <div className={`text-lg font-bold ${getStatusColor(comparison.replay_status)}`}>
          {comparison.replay_status}
        </div>
      </div>
      <div className="bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
        <div className="text-sm text-gray-600 dark:text-gray-400">Identical Steps</div>
        <div className="text-lg font-bold text-green-600">{identicalCount}</div>
      </div>
      <div className="bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
        <div className="text-sm text-gray-600 dark:text-gray-400">Differences</div>
        <div className="text-lg font-bold text-orange-600">{differenceCount}</div>
      </div>
    </div>
  );
}

function ComparisonDetails({ comparison, expandedDiffs, toggleDiff }) {
  if (!comparison?.differences?.length) {
    return null;
  }

  return (
    <div className="p-4 space-y-4">
      <h3 className="text-md font-semibold">Step-by-Step Comparison</h3>

      {comparison.differences.map((diff, idx) => (
        <div key={idx} className="border dark:border-gray-700 rounded-lg overflow-hidden">
          {/* Step Header */}
          <div
            className={`p-3 cursor-pointer flex items-center justify-between ${
              diff.identical ? 'bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800' : 'bg-orange-50 dark:bg-orange-950/30 border-orange-200 dark:border-orange-800'
            }`}
            onClick={() => toggleDiff(idx)}
          >
            <div className="flex items-center gap-3">
              {expandedDiffs.has(idx) ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
              {diff.identical ? (
                <CheckCircle className="w-5 h-5 text-green-600" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-orange-600" />
              )}
              <span className="font-medium text-gray-900 dark:text-gray-100">{diff.step_name}</span>
            </div>
            <span
              className={`text-sm px-2 py-1 rounded ${
                diff.identical
                  ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                  : 'bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300'
              }`}
            >
              {diff.identical ? 'Identical' : 'Different'}
            </span>
          </div>

          {/* Expanded Details */}
          {expandedDiffs.has(idx) && (
            <div className="p-4 bg-white dark:bg-gray-900">
              {diff.identical ? (
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  <p className="mb-2">✓ Outputs match perfectly</p>
                  <details>
                    <summary className="cursor-pointer text-blue-600 hover:text-blue-700">
                      View output
                    </summary>
                    <pre className="mt-2 p-3 bg-gray-50 dark:bg-gray-800 dark:text-gray-200 rounded text-xs overflow-x-auto">
                      {JSON.stringify(diff.original_output, null, 2)}
                    </pre>
                  </details>
                </div>
              ) : (
                <div>
                  <p className="text-sm text-orange-700 mb-3">⚠️ Outputs differ</p>
                  <ReactDiffViewer
                    oldValue={JSON.stringify(diff.original_output, null, 2)}
                    newValue={JSON.stringify(diff.replay_output, null, 2)}
                    splitView={true}
                    leftTitle="Original"
                    rightTitle="Replay"
                    styles={{
                      variables: {
                        light: {
                          diffViewerBackground: '#fafafa',
                          addedBackground: '#e6ffed',
                          removedBackground: '#ffeef0',
                        },
                      },
                    }}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function HistoryCard({ item }) {
  return (
    <div className="bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {item.identical ? (
            <CheckCircle className="w-5 h-5 text-green-600" />
          ) : (
            <XCircle className="w-5 h-5 text-red-600" />
          )}
          <div>
            <div className="font-medium text-sm">
              {item.identical ? 'Identical Replay' : 'Divergent Replay'}
            </div>
            <div className="text-xs text-gray-500">
              {new Date(item.timestamp).toLocaleString()}
            </div>
          </div>
        </div>
        <div className="text-sm text-gray-600 dark:text-gray-400">{item.difference_count} differences</div>
      </div>
    </div>
  );
}

function getStatusColor(status) {
  const statusColors = {
    completed: 'text-green-600',
    failed: 'text-red-600',
    running: 'text-blue-600',
    pending: 'text-gray-600',
  };
  return statusColors[status?.toLowerCase()] || 'text-gray-600';
}
