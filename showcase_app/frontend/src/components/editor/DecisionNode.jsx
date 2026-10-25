import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { GitBranch } from 'lucide-react';

export default memo(({ data, isConnectable }) => {
  return (
    <div className="px-4 py-3 rounded-lg border-2 bg-orange-50 dark:bg-orange-950/40 border-orange-300 dark:border-orange-800 text-orange-700 dark:text-orange-300 shadow-md min-w-[150px]">
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={isConnectable}
        className="w-3 h-3 !bg-orange-500"
      />

      <div className="flex items-center gap-2">
        <GitBranch className="w-4 h-4" />
        <div>
          <div className="font-medium text-sm">{data.label || 'Decision'}</div>
          {data.condition && (
            <div className="text-xs opacity-75 mt-1">{data.condition}</div>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id="true"
        isConnectable={isConnectable}
        className="w-3 h-3 !bg-green-500"
        style={{ top: '30%' }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        isConnectable={isConnectable}
        className="w-3 h-3 !bg-red-500"
        style={{ top: '70%' }}
      />
    </div>
  );
});
