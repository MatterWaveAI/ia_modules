import React from 'react';
import { CheckCircle, XCircle, TrendingUp, ArrowRight } from 'lucide-react';

/**
 * Reflection Pattern Visualizer
 * Shows iterative self-improvement through multiple refinement cycles
 */
export default function ReflectionViz({ data }) {
  if (!data || !data.iterations) {
    return <div className="text-gray-500">No reflection data available</div>;
  }

  const { iterations, final_quality_score, initial_output, final_output } = data;

  return (
    <div className="reflection-viz space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/50 rounded-lg flex items-center justify-center">
          <TrendingUp className="text-purple-600 dark:text-purple-400" size={24} />
        </div>
        <div>
          <h3 className="text-xl font-semibold">Reflection Pattern</h3>
          <p className="text-gray-600 dark:text-gray-400">Iterative self-critique and improvement</p>
        </div>
      </div>

      {/* Quality Improvement Progress */}
      <div className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-gray-800 dark:to-gray-800 p-6 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Quality Improvement</span>
          <span className="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {(final_quality_score * 100).toFixed(0)}%
          </span>
        </div>
        
        {/* Progress Bar */}
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 mb-2">
          <div
            className="bg-gradient-to-r from-purple-500 to-blue-500 h-3 rounded-full transition-all duration-500"
            style={{ width: `${final_quality_score * 100}%` }}
          />
        </div>
        
        <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
          <span>{iterations.length} iterations</span>
          <span>Target: 85%</span>
        </div>
      </div>

      {/* Iteration Timeline */}
      <div className="space-y-4">
        <h4 className="font-semibold text-gray-800 dark:text-gray-100">Refinement Iterations</h4>
        
        {iterations.map((iteration, idx) => (
          <div key={idx} className="relative">
            {/* Connection Line */}
            {idx < iterations.length - 1 && (
              <div className="absolute left-6 top-16 w-0.5 h-full bg-gradient-to-b from-purple-300 dark:from-purple-600 to-transparent" />
            )}
            
            <div className="flex gap-4">
              {/* Iteration Number Badge */}
              <div className={`
                flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center font-bold text-white
                ${iteration.quality_score >= 0.85 
                  ? 'bg-green-500' 
                  : iteration.quality_score >= 0.7 
                    ? 'bg-yellow-500' 
                    : 'bg-red-500'
                }
              `}>
                {iteration.iteration}
              </div>
              
              {/* Iteration Content */}
              <div className="flex-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-4 shadow-sm">
                {/* Quality Score */}
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    Quality Score
                  </span>
                  <div className="flex items-center gap-2">
                    <div className={`
                      px-3 py-1 rounded-full text-sm font-semibold
                      ${iteration.quality_score >= 0.85
                        ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                        : iteration.quality_score >= 0.7
                          ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300'
                          : 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300'
                      }
                    `}>
                      {(iteration.quality_score * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>

                {/* Current Output Preview */}
                <div className="mb-3">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Output</div>
                  <div className="bg-gray-50 dark:bg-gray-800/50 p-3 rounded border border-gray-200 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300">
                    {iteration.output.substring(0, 200)}
                    {iteration.output.length > 200 && '...'}
                  </div>
                </div>

                {/* Critique */}
                <div className="mb-3">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Self-Critique</div>
                  <div className="bg-amber-50 dark:bg-amber-950/30 p-3 rounded border border-amber-200 dark:border-amber-800 text-sm text-gray-700 dark:text-gray-300">
                    {iteration.critique}
                  </div>
                </div>

                {/* Improvements Suggested */}
                {iteration.improvements_suggested && iteration.improvements_suggested.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Improvements</div>
                    <ul className="space-y-1">
                      {iteration.improvements_suggested.map((improvement, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <ArrowRight size={16} className="text-blue-500 mt-0.5 flex-shrink-0" />
                          <span className="text-gray-700 dark:text-gray-300">{improvement}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Success Badge */}
                {iteration.improved_output && (
                  <div className="mt-3 flex items-center gap-2 text-green-600 dark:text-green-400 text-sm font-medium">
                    <CheckCircle size={16} />
                    <span>Quality threshold reached!</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Before/After Comparison */}
      {initial_output && final_output && initial_output !== final_output && (
        <div className="grid md:grid-cols-2 gap-4 mt-6">
          <div>
            <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-2">
              <XCircle size={16} className="text-red-500" />
              Initial Output
            </div>
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-gray-700 dark:text-gray-300">
              {initial_output}
            </div>
          </div>
          
          <div>
            <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-2">
              <CheckCircle size={16} className="text-green-500" />
              Final Output
            </div>
            <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-sm text-gray-700 dark:text-gray-300">
              {final_output}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
