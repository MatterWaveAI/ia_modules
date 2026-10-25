import React from 'react';
import { Target, Clock, CheckCircle2, ArrowRight, GitBranch } from 'lucide-react';

/**
 * Planning Pattern Visualizer
 * Shows multi-step goal decomposition with dependencies
 */
export default function PlanningViz({ data }) {
  if (!data || !data.plan) {
    return <div className="text-gray-500">No planning data available</div>;
  }

  const { goal, plan, estimated_total_time, constraints } = data;

  return (
    <div className="planning-viz space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/50 rounded-lg flex items-center justify-center">
          <Target className="text-blue-600 dark:text-blue-400" size={24} />
        </div>
        <div>
          <h3 className="text-xl font-semibold">Planning Pattern</h3>
          <p className="text-gray-600 dark:text-gray-400">Multi-step goal decomposition</p>
        </div>
      </div>

      {/* Goal Card */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-800 dark:to-gray-800 p-6 rounded-lg border border-blue-200 dark:border-blue-800">
        <div className="flex items-start gap-3">
          <Target className="text-blue-600 dark:text-blue-400 mt-1" size={20} />
          <div className="flex-1">
            <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Primary Goal</div>
            <div className="text-lg font-semibold text-gray-800 dark:text-gray-100">{goal}</div>
          </div>
        </div>

        {/* Constraints */}
        {constraints && Object.keys(constraints).length > 0 && (
          <div className="mt-4 pt-4 border-t border-blue-200 dark:border-blue-800">
            <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Constraints</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(constraints).map(([key, value]) => (
                <span key={key} className="px-3 py-1 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium">
                  {key}: {String(value)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800 text-center">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{plan.length}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Total Steps</div>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800 text-center">
          <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{estimated_total_time}m</div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Est. Time</div>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800 text-center">
          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {plan.filter(s => s.dependencies?.length > 0).length}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Dependencies</div>
        </div>
      </div>

      {/* Execution Plan Timeline */}
      <div className="space-y-4">
        <h4 className="font-semibold text-gray-800 dark:text-gray-100">Execution Plan</h4>
        
        {plan.map((step, idx) => (
          <div key={idx} className="relative">
            {/* Connection Line */}
            {idx < plan.length - 1 && (
              <div className="absolute left-6 top-20 w-0.5 h-full bg-gradient-to-b from-blue-300 dark:from-blue-600 to-transparent" />
            )}
            
            <div className="flex gap-4">
              {/* Step Number */}
              <div className="flex-shrink-0 w-12 h-12 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold shadow-md">
                {step.step_number}
              </div>
              
              {/* Step Card */}
              <div className="flex-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-5 shadow-sm hover:shadow-md transition-shadow">
                {/* Step Header */}
                <div className="flex items-start justify-between mb-3">
                  <h5 className="font-semibold text-gray-800 dark:text-gray-100 text-lg flex-1">
                    {step.subgoal}
                  </h5>
                  <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                    <Clock size={16} />
                    <span className="text-sm">{step.estimated_duration}m</span>
                  </div>
                </div>

                {/* Reasoning */}
                <div className="mb-3">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Why this step?</div>
                  <div className="bg-blue-50 dark:bg-blue-950/30 p-3 rounded border border-blue-100 dark:border-blue-800 text-sm text-gray-700 dark:text-gray-300 italic">
                    {step.reasoning}
                  </div>
                </div>

                {/* Dependencies */}
                {step.dependencies && step.dependencies.length > 0 && (
                  <div className="mb-3">
                    <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Dependencies</div>
                    <div className="flex items-center gap-2">
                      <GitBranch size={16} className="text-purple-500" />
                      <div className="flex flex-wrap gap-2">
                        {step.dependencies.map((dep, i) => (
                          <span key={i} className="px-2 py-1 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 rounded text-xs font-medium">
                            Step {dep}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Success Criteria */}
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Success Criteria</div>
                  <ul className="space-y-1">
                    {step.success_criteria.map((criterion, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <CheckCircle2 size={16} className="text-green-500 mt-0.5 flex-shrink-0" />
                        <span className="text-gray-700 dark:text-gray-300">{criterion}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Gantt-style Timeline Visualization */}
      <div className="mt-6">
        <h4 className="font-semibold text-gray-800 dark:text-gray-100 mb-4">Timeline Overview</h4>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-4">
          <div className="space-y-2">
            {plan.map((step, idx) => {
              const startTime = plan.slice(0, idx).reduce((sum, s) => sum + s.estimated_duration, 0);
              const duration = step.estimated_duration;
              const totalTime = estimated_total_time;
              const startPercent = (startTime / totalTime) * 100;
              const widthPercent = (duration / totalTime) * 100;
              
              return (
                <div key={idx} className="relative h-10">
                  <div className="absolute inset-y-0 left-0 flex items-center text-xs text-gray-600 dark:text-gray-400 w-20">
                    Step {step.step_number}
                  </div>
                  <div className="absolute inset-y-0 left-24 right-0">
                    <div
                      className="absolute h-8 bg-gradient-to-r from-blue-400 to-blue-500 rounded flex items-center justify-center text-white text-xs font-medium shadow"
                      style={{
                        left: `${startPercent}%`,
                        width: `${widthPercent}%`
                      }}
                    >
                      {duration}m
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          
          {/* Time Scale */}
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>0m</span>
              <span>{Math.floor(estimated_total_time / 2)}m</span>
              <span>{estimated_total_time}m</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
