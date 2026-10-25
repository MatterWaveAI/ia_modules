import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Play, CheckCircle, XCircle, Loader, Circle } from 'lucide-react';

export default memo(({ data, isConnectable }) => {
  const status = data.status || 'pending';
  const { icon: Icon, color, bgColor } = getStatusStyle(status);

  const inputs = data.inputs || [];
  const outputs = data.outputs || [];
  const hasNamedPorts = inputs.length > 0 || outputs.length > 0;

  return (
    <div
      className={`rounded-lg border-2 ${bgColor} ${color} shadow-md min-w-[180px] hover:shadow-lg transition-shadow`}
    >
      {/* Default single handles when no named ports */}
      {!hasNamedPorts && (
        <Handle
          type="target"
          position={Position.Left}
          isConnectable={isConnectable}
          className="w-3 h-3 !bg-blue-500"
        />
      )}

      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-2">
        <Icon className="w-4 h-4 flex-shrink-0" />
        <div className="min-w-0">
          <div className="font-medium text-sm truncate">{data.label}</div>
          {data.stepType && <div className="text-xs opacity-75">{data.stepType}</div>}
        </div>
      </div>

      {data.duration && (
        <div className="text-xs px-4 pb-1 opacity-75">{formatDuration(data.duration)}</div>
      )}

      {/* Named ports section */}
      {hasNamedPorts && (
        <div className="border-t border-current/10 flex text-[10px] leading-none">
          {/* Input ports (left side) */}
          <div className="flex-1 border-r border-current/10">
            {inputs.length > 0 ? inputs.map((name) => (
              <div key={`in-${name}`} className="relative pl-4 pr-2 py-[5px]">
                <Handle
                  type="target"
                  position={Position.Left}
                  id={`in-${name}`}
                  isConnectable={isConnectable}
                  className="!w-2 !h-2 !bg-blue-400"
                />
                <span className="text-blue-600 dark:text-blue-400 font-mono truncate block">{name}</span>
              </div>
            )) : (
              <div className="pl-4 pr-2 py-[5px] opacity-40 italic">no inputs</div>
            )}
          </div>

          {/* Output ports (right side) */}
          <div className="flex-1">
            {outputs.length > 0 ? outputs.map((name) => (
              <div key={`out-${name}`} className="relative pl-2 pr-4 py-[5px] text-right">
                <Handle
                  type="source"
                  position={Position.Right}
                  id={`out-${name}`}
                  isConnectable={isConnectable}
                  className="!w-2 !h-2 !bg-green-400"
                />
                <span className="text-green-600 dark:text-green-400 font-mono truncate block">{name}</span>
              </div>
            )) : (
              <div className="pl-2 pr-4 py-[5px] opacity-40 italic text-right">no outputs</div>
            )}
          </div>
        </div>
      )}

      {/* Default single handles when no named ports */}
      {!hasNamedPorts && (
        <Handle
          type="source"
          position={Position.Right}
          isConnectable={isConnectable}
          className="w-3 h-3 !bg-blue-500"
        />
      )}
    </div>
  );
});

function getStatusStyle(status) {
  switch (status) {
    case 'completed':
      return {
        icon: CheckCircle,
        color: 'text-green-700 dark:text-green-300',
        bgColor: 'bg-green-50 dark:bg-green-950/40 border-green-300 dark:border-green-800',
      };
    case 'failed':
    case 'error':
      return {
        icon: XCircle,
        color: 'text-red-700 dark:text-red-300',
        bgColor: 'bg-red-50 dark:bg-red-950/40 border-red-300 dark:border-red-800',
      };
    case 'running':
      return {
        icon: Loader,
        color: 'text-yellow-700 dark:text-yellow-300',
        bgColor: 'bg-yellow-50 dark:bg-yellow-950/40 border-yellow-300 dark:border-yellow-800',
      };
    case 'pending':
    default:
      return {
        icon: Circle,
        color: 'text-gray-700 dark:text-gray-300',
        bgColor: 'bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-700',
      };
  }
}

function formatDuration(ms) {
  if (!ms) return '';
  const seconds = Math.floor(ms / 1000);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
