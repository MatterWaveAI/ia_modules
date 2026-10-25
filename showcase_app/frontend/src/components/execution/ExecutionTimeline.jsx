import { useMemo } from 'react';
import { Gantt, ViewMode } from 'gantt-task-react';
import 'gantt-task-react/dist/index.css';
import { Clock, Activity, CheckCircle, XCircle, Loader } from 'lucide-react';
import { parseBackendTimestamp } from '../../lib/utils';

export default function ExecutionTimeline({ execution, pipeline }) {
  const { tasks, metrics } = useMemo(() => {
    // Build full step list from the pipeline config, then overlay execution
    // status. We wait for the pipeline query to resolve before rendering any
    // rows — otherwise the first paint shows "Step 2 / Step 3" placeholders
    // until the config lands. One render is cheap; a flicker is ugly.
    const pipelineSteps = pipeline?.config?.steps || [];
    const executedSteps = execution?.steps || [];

    // Index executed steps by step_name for overlay.
    const executedByName = new Map();
    executedSteps.forEach((s) => {
      if (s.step_name) executedByName.set(s.step_name, s);
    });

    // Use the step id (e.g. "data_ingestor") rather than the human name so
    // the Gantt rows match the status card's "Currently executing: X" label.
    const baseSteps = pipelineSteps.map((ps) => {
      const key = ps.id || ps.name;
      const executed = executedByName.get(key);
      return {
        step_name: key,
        status: executed?.status || 'pending',
        started_at: executed?.started_at,
        completed_at: executed?.completed_at,
        duration_ms: executed?.duration_ms,
      };
    });

    // Anchor timeline to the execution start.
    const anchor = execution?.started_at
      ? parseBackendTimestamp(execution.started_at)
      : new Date();

    // Convert to Gantt tasks. For pending steps, use a tiny placeholder bar
    // at the end of the timeline so they show up as a row.
    const ganttTasks = baseSteps.map((step, index) => {
      let start;
      let end;

      if (step.started_at) {
        start = parseBackendTimestamp(step.started_at);
        if (step.completed_at) {
          end = parseBackendTimestamp(step.completed_at);
        } else if (step.status === 'running') {
          end = new Date();
        } else {
          end = new Date(start.getTime() + 1000);
        }
      } else {
        // Pending step — place a 1s placeholder bar just after anchor
        // so the row renders. Offset by index to avoid identical ranges.
        const offset = anchor.getTime() + index * 1000;
        start = new Date(offset);
        end = new Date(offset + 1000);
      }

      // Ensure end is strictly after start.
      if (end.getTime() <= start.getTime()) {
        end = new Date(start.getTime() + 1000);
      }

      return {
        id: `step-${index}-${step.step_name}`,
        name: step.step_name || `Step ${index + 1}`,
        start,
        end,
        progress: getStepProgress(step),
        type: 'task',
        styles: getTaskStyles(step.status),
        isDisabled: step.status === 'pending',
        hideChildren: false,
      };
    });

    // Metrics. Prefer the execution record's own total_steps (set at start
    // from the pipeline config) so the header is correct even while the
    // async `pipeline` query is still loading.
    const total = execution?.total_steps || baseSteps.length;
    const completed = baseSteps.filter((s) => s.status === 'completed').length;
    const failed = baseSteps.filter((s) => s.status === 'failed' || s.status === 'error').length;
    const running = baseSteps.filter((s) => s.status === 'running').length;

    const startMs = execution?.started_at ? parseBackendTimestamp(execution.started_at).getTime() : null;
    const endMs = execution?.completed_at
      ? parseBackendTimestamp(execution.completed_at).getTime()
      : Date.now();
    const totalDuration = startMs ? Math.max(endMs - startMs, 0) : 0;

    return {
      tasks: ganttTasks,
      metrics: { total, completed, failed, running, duration: totalDuration },
    };
  }, [execution, pipeline]);

  if (!execution) {
    return (
      <div className="p-8 text-center text-gray-500">
        <Clock className="w-12 h-12 mx-auto mb-4 text-gray-400" />
        <p>No execution data available</p>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500">
        <Activity className="w-12 h-12 mx-auto mb-4 text-gray-400" />
        <p>No steps to display</p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-md border border-gray-200 dark:border-gray-800">
      {/* Header with Metrics */}
      <div className="p-4 border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-gray-900 dark:text-gray-100">
          <Activity className="w-5 h-5" />
          Execution Timeline
        </h2>

        <div className="grid grid-cols-5 gap-4">
          <MetricCard
            icon={<Activity className="w-4 h-4" />}
            label="Total Steps"
            value={metrics.total}
            color="text-blue-600 dark:text-blue-400"
          />
          <MetricCard
            icon={<CheckCircle className="w-4 h-4" />}
            label="Completed"
            value={metrics.completed}
            color="text-green-600 dark:text-green-400"
          />
          <MetricCard
            icon={<XCircle className="w-4 h-4" />}
            label="Failed"
            value={metrics.failed}
            color="text-red-600 dark:text-red-400"
          />
          <MetricCard
            icon={<Loader className="w-4 h-4" />}
            label="Running"
            value={metrics.running}
            color="text-yellow-600 dark:text-yellow-400"
          />
          <MetricCard
            icon={<Clock className="w-4 h-4" />}
            label="Duration"
            value={formatDuration(metrics.duration)}
            color="text-purple-600 dark:text-purple-400"
          />
        </div>
      </div>

      {/* Gantt Chart */}
      <div className="p-4 overflow-x-auto">
        <Gantt
          tasks={tasks}
          viewMode={ViewMode.Minute}
          columnWidth={65}
          listCellWidth="155px"
          barCornerRadius={4}
          barProgressColor="#3b82f6"
          barProgressSelectedColor="#2563eb"
          barBackgroundColor="#dbeafe"
          barBackgroundSelectedColor="#bfdbfe"
          todayColor="rgba(252, 165, 165, 0.3)"
          handleWidth={8}
          fontSize="12px"
          rowHeight={40}
          headerHeight={50}
        />
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value, color }) {
  return (
    <div className="bg-white dark:bg-gray-900 p-3 rounded-lg border dark:border-gray-700">
      <div className="flex items-center gap-2 mb-1">
        <span className={color}>{icon}</span>
        <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>
      </div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function getStepProgress(step) {
  switch (step.status) {
    case 'completed':
      return 100;
    case 'running':
      return 50;
    case 'failed':
    case 'error':
      return 100;
    case 'pending':
    default:
      return 0;
  }
}

function getTaskStyles(status) {
  switch (status) {
    case 'completed':
      return {
        backgroundColor: '#10b981',
        backgroundSelectedColor: '#059669',
        progressColor: '#047857',
        progressSelectedColor: '#065f46'
      };
    case 'failed':
    case 'error':
      return {
        backgroundColor: '#ef4444',
        backgroundSelectedColor: '#dc2626',
        progressColor: '#b91c1c',
        progressSelectedColor: '#991b1b'
      };
    case 'running':
      return {
        backgroundColor: '#f59e0b',
        backgroundSelectedColor: '#d97706',
        progressColor: '#b45309',
        progressSelectedColor: '#92400e'
      };
    case 'pending':
    default:
      return {
        backgroundColor: '#9ca3af',
        backgroundSelectedColor: '#6b7280',
        progressColor: '#4b5563',
        progressSelectedColor: '#374151'
      };
  }
}

function formatDuration(ms) {
  if (!ms || ms < 0) return '0s';

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  } else {
    return `${seconds}s`;
  }
}
