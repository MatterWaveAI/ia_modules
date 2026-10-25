import React from 'react';
import { Search, RefreshCw, TrendingUp, FileText, Star } from 'lucide-react';

/**
 * Agentic RAG Pattern Visualizer
 * Shows query refinement and relevance evaluation
 */
export default function AgenticRAGViz({ data }) {
  if (!data || !data.iterations) {
    return <div className="text-gray-500">No RAG data available</div>;
  }

  const { initial_query, final_query, iterations, final_relevance } = data;

  return (
    <div className="agentic-rag-viz space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 bg-green-100 dark:bg-green-900/50 rounded-lg flex items-center justify-center">
          <Search className="text-green-600 dark:text-green-400" size={24} />
        </div>
        <div>
          <h3 className="text-xl font-semibold">Agentic RAG Pattern</h3>
          <p className="text-gray-600 dark:text-gray-400">Iterative query refinement and retrieval</p>
        </div>
      </div>

      {/* Query Evolution */}
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-gray-800 dark:to-gray-800 p-6 rounded-lg border border-green-200 dark:border-green-800">
        <div className="space-y-4">
          <div>
            <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Initial Query</div>
            <div className="bg-white dark:bg-gray-900 p-3 rounded border border-green-200 dark:border-green-800 text-gray-800 dark:text-gray-100">
              {initial_query}
            </div>
          </div>
          
          {initial_query !== final_query && (
            <>
              <div className="flex justify-center">
                <RefreshCw className="text-green-500" size={20} />
              </div>
              
              <div>
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Refined Query</div>
                <div className="bg-gradient-to-r from-green-100 to-emerald-100 dark:from-green-900/40 dark:to-emerald-900/40 p-3 rounded border border-green-300 dark:border-green-700 text-gray-800 dark:text-gray-100 font-medium">
                  {final_query}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Relevance Improvement */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800 text-center">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">{iterations.length}</div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Iterations</div>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800 text-center">
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
            {(final_relevance * 100).toFixed(0)}%
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Final Relevance</div>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800 text-center">
          <div className="text-2xl font-bold text-teal-600 dark:text-teal-400">
            {iterations.reduce((sum, it) => sum + it.documents_retrieved, 0)}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Total Docs</div>
        </div>
      </div>

      {/* Iteration Timeline */}
      <div className="space-y-4">
        <h4 className="font-semibold text-gray-800 dark:text-gray-100">Retrieval Iterations</h4>
        
        {iterations.map((iteration, idx) => (
          <div key={idx} className="relative">
            {/* Connection Line */}
            {idx < iterations.length - 1 && (
              <div className="absolute left-6 top-16 w-0.5 h-full bg-gradient-to-b from-green-300 dark:from-green-600 to-transparent" />
            )}
            
            <div className="flex gap-4">
              {/* Iteration Badge */}
              <div className={`
                flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center font-bold text-white shadow-md
                ${iteration.average_relevance >= 0.8 
                  ? 'bg-green-500' 
                  : iteration.average_relevance >= 0.6 
                    ? 'bg-yellow-500' 
                    : 'bg-orange-500'
                }
              `}>
                {iteration.iteration}
              </div>
              
              {/* Iteration Content */}
              <div className="flex-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-5 shadow-sm">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Search size={18} className="text-gray-600 dark:text-gray-400" />
                    <span className="font-medium text-gray-800 dark:text-gray-100">
                      Query {iteration.iteration}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <TrendingUp size={16} className={
                      iteration.average_relevance >= 0.8 ? 'text-green-500' :
                      iteration.average_relevance >= 0.6 ? 'text-yellow-500' :
                      'text-orange-500'
                    } />
                    <span className={`
                      px-3 py-1 rounded-full text-sm font-semibold
                      ${iteration.average_relevance >= 0.8
                        ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                        : iteration.average_relevance >= 0.6
                          ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300'
                          : 'bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300'
                      }
                    `}>
                      {(iteration.average_relevance * 100).toFixed(0)}% relevant
                    </span>
                  </div>
                </div>

                {/* Query Text */}
                <div className="mb-4">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Query</div>
                  <div className="bg-gray-50 dark:bg-gray-800/50 p-3 rounded border border-gray-200 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300">
                    {iteration.query}
                  </div>
                </div>

                {/* Retrieved Documents */}
                <div className="mb-4">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
                    Retrieved Documents ({iteration.documents_retrieved})
                  </div>
                  <div className="space-y-2">
                    {iteration.documents.map((doc, docIdx) => (
                      <div key={docIdx} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded p-3">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2 flex-1">
                            <FileText size={16} className="text-blue-500 flex-shrink-0" />
                            <span className="font-medium text-sm text-gray-800 dark:text-gray-100">{doc.title}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Star size={14} className={
                              doc.relevance_score >= 0.8 ? 'text-yellow-500 fill-yellow-500' :
                              doc.relevance_score >= 0.6 ? 'text-yellow-400 fill-yellow-400' :
                              'text-gray-400'
                            } />
                            <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                              {(doc.relevance_score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
                          {doc.content_preview}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Refined Query (if exists) */}
                {iteration.refined_query && iteration.refined_query !== iteration.query && (
                  <div className="pt-3 border-t border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-2 mb-2">
                      <RefreshCw size={16} className="text-green-500" />
                      <div className="text-xs font-medium text-gray-500 dark:text-gray-400">
                        Query Refinement Applied
                      </div>
                    </div>
                    <div className="bg-green-50 dark:bg-green-950/30 p-3 rounded border border-green-200 dark:border-green-800 text-sm text-gray-700 dark:text-gray-300">
                      {iteration.refined_query}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Relevance Trend Chart */}
      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-6">
        <h4 className="font-semibold text-gray-800 dark:text-gray-100 mb-4">Relevance Improvement Trend</h4>
        <div className="flex items-end gap-4 h-40">
          {iterations.map((iteration, idx) => {
            const height = iteration.average_relevance * 100;
            return (
              <div key={idx} className="flex-1 flex flex-col items-center">
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  {(iteration.average_relevance * 100).toFixed(0)}%
                </div>
                <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-t flex items-end" style={{ height: '120px' }}>
                  <div
                    className={`
                      w-full rounded-t transition-all duration-500
                      ${iteration.average_relevance >= 0.8 
                        ? 'bg-gradient-to-t from-green-500 to-green-400' 
                        : iteration.average_relevance >= 0.6 
                          ? 'bg-gradient-to-t from-yellow-500 to-yellow-400' 
                          : 'bg-gradient-to-t from-orange-500 to-orange-400'
                      }
                    `}
                    style={{ height: `${height}%` }}
                  />
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">Iter {iteration.iteration}</div>
              </div>
            );
          })}
        </div>
        
        {/* Target Line */}
        <div className="relative mt-4">
          <div className="absolute inset-x-0 border-t-2 border-dashed border-green-400" style={{ top: '-80px' }} />
          <div className="text-xs text-green-600 dark:text-green-400 font-medium">Target: 80% relevance</div>
        </div>
      </div>
    </div>
  );
}
