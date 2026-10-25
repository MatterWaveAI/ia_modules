import { Box, Code, MessageSquare, Bot, Network, Users, UserCheck } from 'lucide-react';

// Each entry maps 1:1 to a real Step class in ia_modules/pipeline/.
// Keep this in sync with the step modules under ia_modules/pipeline/.
const moduleCategories = [
  {
    name: 'Built-in Steps',
    modules: [
      { type: 'LLMStep', label: 'LLM', icon: MessageSquare, description: 'Prompt in, text out' },
      { type: 'FunctionStep', label: 'Function', icon: Code, description: 'Wrap an async callable' },
      { type: 'AgentStep', label: 'Agent', icon: Bot, description: 'Run a CLI agent locally' },
      { type: 'A2AStep', label: 'A2A', icon: Network, description: 'Dispatch to a remote A2A server' },
    ],
  },
  {
    name: 'Orchestration',
    modules: [
      { type: 'ParallelStep', label: 'Parallel', icon: Box, description: 'Fan-out to concurrent children' },
      { type: 'OrchestratorStep', label: 'Orchestrator', icon: Users, description: 'Run a collaboration pattern' },
    ],
  },
  {
    name: 'Human-in-the-Loop',
    modules: [
      { type: 'HumanInputStep', label: 'Human Input', icon: UserCheck, description: 'Pause for human input' },
    ],
  },
];

export default function ModulePalette({ onAddStep }) {
  return (
    <div className="w-64 bg-gray-50 dark:bg-gray-800/50 border-r dark:border-gray-700 p-4 overflow-y-auto">
      <h3 className="font-semibold text-gray-700 dark:text-gray-300 mb-4">Module Palette</h3>

      <div className="space-y-4">
        {moduleCategories.map((category) => (
          <div key={category.name}>
            <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">{category.name}</h4>
            <div className="space-y-2">
              {category.modules.map((module) => (
                <ModuleCard key={module.type} module={module} onAdd={() => onAddStep(module.type)} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
        <p className="text-xs text-blue-700 dark:text-blue-300">
          <strong>Tip:</strong> Drag modules onto the canvas or click to add. Connect nodes by dragging from one
          node's edge to another.
        </p>
      </div>
    </div>
  );
}

function ModuleCard({ module, onAdd }) {
  const Icon = module.icon;

  return (
    <button
      onClick={onAdd}
      className="w-full p-3 bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-lg hover:border-blue-500 hover:shadow-md transition-all text-left group"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded group-hover:bg-blue-100 dark:group-hover:bg-blue-900/40 transition-colors">
          <Icon className="w-4 h-4 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-gray-900 dark:text-gray-100">{module.label}</div>
          <div className="text-xs text-gray-500 mt-0.5">{module.description}</div>
        </div>
      </div>
    </button>
  );
}
