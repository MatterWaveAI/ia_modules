import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Box } from 'lucide-react';

export default memo(({ data, isConnectable }) => {
  return (
    <div className="px-4 py-3 rounded-lg border-2 bg-purple-50 dark:bg-purple-950/40 border-purple-300 dark:border-purple-800 text-purple-700 dark:text-purple-300 shadow-md min-w-[180px]">
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={isConnectable}
        className="w-3 h-3 !bg-purple-500"
      />

      <div className="flex items-center gap-2 mb-2">
        <Box className="w-4 h-4" />
        <div className="font-medium text-sm">{data.label || 'Parallel Group'}</div>
      </div>

      {data.steps && (
        <div className="text-xs opacity-75">
          {data.steps.length} parallel steps
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        isConnectable={isConnectable}
        className="w-3 h-3 !bg-purple-500"
      />
    </div>
  );
});
