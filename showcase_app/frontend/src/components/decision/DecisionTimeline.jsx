import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { GitBranch, CircleDot, TrendingUp, FileText, Download, ChevronRight, ChevronDown } from 'lucide-react';
import ReactJson from '@microlink/react-json-view';

const API_BASE = import.meta.env.VITE_API_URL || '';

export default function DecisionTimeline({ jobId }) {
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const [selectedNode, setSelectedNode] = useState(null);

  // Fetch decision trail
  const { data: trail, isLoading: trailLoading } = useQuery({
    queryKey: ['decision-trail', jobId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/reliability/decision-trail/${jobId}`);
      if (!response.ok) throw new Error('Failed to fetch decision trail');
      return response.json();
    },
    enabled: !!jobId
  });

  // Fetch execution path
  const { data: pathData } = useQuery({
    queryKey: ['execution-path', jobId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/reliability/decision-trail/${jobId}/path`);
      if (!response.ok) throw new Error('Failed to fetch execution path');
      return response.json();
    },
    enabled: !!jobId
  });

  // Fetch evidence for selected node
  const { data: evidenceData } = useQuery({
    queryKey: ['decision-evidence', jobId, selectedNode],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE}/api/reliability/decision-trail/${jobId}/evidence/${selectedNode}`
      );
      if (!response.ok) throw new Error('Failed to fetch evidence');
      return response.json();
    },
    enabled: !!jobId && !!selectedNode
  });

  const toggleNode = (nodeId) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const handleExport = async (format) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/reliability/decision-trail/${jobId}/export?format=${format}`
      );
      const data = await response.json();
      
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `decision-trail-${jobId}.${format}`;
      a.click();
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  if (!jobId) {
    return null;
  }

  // Don't render empty panel when trail has no nodes
  if (!trailLoading && !trail?.nodes?.length) {
    return null;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <GitBranch className="w-5 h-5" />
            Decision Trail
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => handleExport('json')}
              className="px-3 py-1 text-sm bg-white dark:bg-gray-900 border dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              JSON
            </button>
            <button
              onClick={() => handleExport('graphviz')}
              className="px-3 py-1 text-sm bg-white dark:bg-gray-900 border dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              DOT
            </button>
            <button
              onClick={() => handleExport('mermaid')}
              className="px-3 py-1 text-sm bg-white dark:bg-gray-900 border dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Mermaid
            </button>
          </div>
        </div>

        {/* Statistics */}
        {trail?.statistics && (
          <div className="grid grid-cols-4 gap-4">
            <StatCard label="Total Nodes" value={trail.statistics.total_nodes} />
            <StatCard label="Decision Points" value={trail.statistics.decision_points} />
            <StatCard label="Paths Taken" value={trail.statistics.paths_taken} />
            <StatCard
              label="Avg Confidence"
              value={`${(trail.statistics.average_confidence * 100).toFixed(1)}%`}
            />
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {trailLoading ? (
          <div className="p-8 text-center text-gray-500">Loading decision trail...</div>
        ) : !trail?.nodes?.length ? (
          <div className="p-8 text-center text-gray-500">No decision trail available</div>
        ) : (
          <div className="p-4">
            {/* Execution Path */}
            {pathData?.path && pathData.path.length > 0 && (
              <div className="mb-6">
                <h3 className="text-md font-semibold mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Execution Path
                </h3>
                <div className="space-y-2">
                  {pathData.path.map((step, idx) => (
                    <PathStep key={idx} step={step} isLast={idx === pathData.path.length - 1} />
                  ))}
                </div>
              </div>
            )}

            {/* Decision Nodes */}
            <h3 className="text-md font-semibold mb-3 flex items-center gap-2">
              <CircleDot className="w-4 h-4" />
              Decision Nodes
            </h3>
            <div className="space-y-3">
              {trail.nodes.map((node) => (
                <DecisionNodeCard
                  key={node.id}
                  node={node}
                  isExpanded={expandedNodes.has(node.id)}
                  isSelected={selectedNode === node.id}
                  onToggle={() => toggleNode(node.id)}
                  onSelect={() => setSelectedNode(node.id)}
                  evidence={selectedNode === node.id ? evidenceData?.evidence : null}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
      <div className="text-sm text-gray-600 dark:text-gray-400">{label}</div>
      <div className="text-xl font-bold text-blue-600">{value}</div>
    </div>
  );
}

function PathStep({ step, isLast }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex flex-col items-center">
        <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 flex items-center justify-center font-semibold text-sm">
          {step.step}
        </div>
        {!isLast && <div className="w-0.5 h-8 bg-blue-200 dark:bg-blue-800 my-1" />}
      </div>
      <div className="flex-1 bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
        <div className="font-medium">{step.decision_type}</div>
        <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">{step.decision}</div>
        <div className="text-xs text-gray-500 mt-1">
          Outcome: <span className="font-medium">{step.outcome}</span>
        </div>
      </div>
    </div>
  );
}

function DecisionNodeCard({ node, isExpanded, isSelected, onToggle, onSelect, evidence }) {
  const confidenceColor =
    node.confidence >= 0.8 ? 'text-green-600' : node.confidence >= 0.6 ? 'text-yellow-600' : 'text-red-600';

  return (
    <div
      className={`border rounded-lg overflow-hidden ${
        isSelected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-200 dark:border-gray-700'
      }`}
    >
      {/* Node Header */}
      <div
        className="p-3 bg-gray-50 dark:bg-gray-800/50 cursor-pointer flex items-center justify-between hover:bg-gray-100 dark:hover:bg-gray-800"
        onClick={onSelect}
      >
        <div className="flex items-center gap-3 flex-1">
          <button onClick={(e) => { e.stopPropagation(); onToggle(); }} className="text-gray-600 dark:text-gray-400">
            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
          <CircleDot className="w-4 h-4 text-blue-600" />
          <div className="flex-1">
            <div className="font-medium">{node.label}</div>
            <div className="text-sm text-gray-600 dark:text-gray-400">{node.type}</div>
          </div>
        </div>
        <div className={`text-sm font-semibold ${confidenceColor}`}>
          {(node.confidence * 100).toFixed(0)}%
        </div>
      </div>

      {/* Node Details */}
      {isExpanded && (
        <div className="p-4 bg-white dark:bg-gray-900 space-y-3">
          {/* Decision */}
          {node.decision && (
            <div>
              <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Decision</div>
              <div className="text-sm text-gray-600 dark:text-gray-400">{node.decision}</div>
            </div>
          )}

          {/* Metadata */}
          {node.metadata && Object.keys(node.metadata).length > 0 && (
            <div>
              <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Metadata</div>
              <ReactJson
                src={node.metadata}
                collapsed={1}
                displayDataTypes={false}
                displayObjectSize={false}
                enableClipboard={false}
                style={{ fontSize: '12px' }}
              />
            </div>
          )}

          {/* Evidence */}
          {evidence && evidence.length > 0 && (
            <div>
              <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Evidence ({evidence.length})
              </div>
              <div className="space-y-2">
                {evidence.map((item, idx) => (
                  <EvidenceCard key={idx} evidence={item} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceCard({ evidence }) {
  const typeColors = {
    direct: 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300',
    inferred: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300',
    contextual: 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300',
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-800/50 p-3 rounded border dark:border-gray-700">
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs px-2 py-1 rounded ${typeColors[evidence.type] || 'bg-gray-100 text-gray-700'}`}>
          {evidence.type}
        </span>
        <div className="text-xs text-gray-500">
          Weight: {evidence.weight} | Confidence: {(evidence.confidence * 100).toFixed(0)}%
        </div>
      </div>
      <div className="text-sm text-gray-700 dark:text-gray-300 mb-1 font-medium">{evidence.source}</div>
      <div className="text-sm text-gray-600 dark:text-gray-400">{evidence.content}</div>
    </div>
  );
}
