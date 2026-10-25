import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, X, Check, AlertCircle, Database, FileCode } from 'lucide-react';
import CodeEditor from './CodeEditor';

const API_BASE = import.meta.env.VITE_API_URL || '';

/**
 * StepCodeEditor - Component for viewing and editing step Python code
 *
 * Features:
 * - Load step code from database
 * - Syntax highlighted Python editor
 * - Save changes back to database
 * - Validation before save
 * - Shows storage location (DB vs filesystem)
 */
export default function StepCodeEditor({ pipelineId, stepId, onClose }) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  const [validationError, setValidationError] = useState(null);

  // Fetch step code from database
  const { data: stepModule, isLoading, error } = useQuery({
    queryKey: ['step-module', pipelineId, stepId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE}/api/pipelines/${pipelineId}/steps/${stepId}/code`
      );
      if (!response.ok) {
        throw new Error('Failed to load step code');
      }
      return response.json();
    },
    enabled: !!pipelineId && !!stepId,
  });

  useEffect(() => {
    if (stepModule) {
      setCode(stepModule.source_code);
      setHasChanges(false);
    }
  }, [stepModule]);

  // Validation mutation
  const validateMutation = useMutation({
    mutationFn: async (codeToValidate) => {
      const response = await fetch(
        `${API_BASE}/api/pipelines/${pipelineId}/steps/${stepId}/validate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_code: codeToValidate }),
        }
      );
      return response.json();
    },
    onSuccess: (data) => {
      if (!data.valid) {
        setValidationError(data.error);
      } else {
        setValidationError(null);
      }
    },
  });

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async (newCode) => {
      // Validate first
      const validationResult = await validateMutation.mutateAsync(newCode);
      if (!validationResult.valid) {
        throw new Error(validationResult.error);
      }

      const response = await fetch(
        `${API_BASE}/api/pipelines/${pipelineId}/steps/${stepId}/code`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_code: newCode }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to save step code');
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['step-module', pipelineId, stepId]);
      setHasChanges(false);
      setValidationError(null);
    },
    onError: (error) => {
      setValidationError(error.message);
    },
  });

  const handleCodeChange = (newCode) => {
    setCode(newCode);
    setHasChanges(true);
    setValidationError(null);
  };

  const handleSave = () => {
    saveMutation.mutate(code);
  };

  const handleValidate = () => {
    validateMutation.mutate(code);
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading step code...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 dark:text-red-400">{error.message}</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
            Step code may not be in database. Try importing the pipeline first.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-gray-50 dark:bg-gray-800/50">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <FileCode className="w-5 h-5 text-blue-600" />
            <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">{stepModule?.class_name || 'Step Code'}</h3>
            {hasChanges && (
              <span className="text-xs bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 px-2 py-1 rounded">
                ● Unsaved changes
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{stepModule?.module_path}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleValidate}
            disabled={!hasChanges || validateMutation.isLoading}
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 flex items-center gap-2 text-sm disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            Validate
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || saveMutation.isLoading || !!validationError}
            className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            {saveMutation.isLoading ? 'Saving...' : 'Save'}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Validation Error */}
      {validationError && (
        <div className="bg-red-50 dark:bg-red-950/40 border-l-4 border-red-500 p-4">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-red-800 dark:text-red-300">Validation Error</h4>
              <p className="text-sm text-red-700 dark:text-red-400 mt-1 font-mono">{validationError}</p>
            </div>
          </div>
        </div>
      )}

      {/* Success Message */}
      {saveMutation.isSuccess && !hasChanges && (
        <div className="bg-green-50 dark:bg-green-950/40 border-l-4 border-green-500 p-3">
          <div className="flex items-center gap-2">
            <Check className="w-5 h-5 text-green-500" />
            <p className="text-sm text-green-700 dark:text-green-300">Step code saved successfully</p>
          </div>
        </div>
      )}

      {/* Code Editor */}
      <div className="flex-1 overflow-hidden">
        <CodeEditor value={code} onChange={handleCodeChange} language="python" />
      </div>

      {/* Footer with metadata */}
      {stepModule && (
        <div className="p-3 border-t bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1">
                <Database className="w-3 h-3" />
                <span className="font-medium">Storage:</span>
                <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded">Database</span>
              </div>
              <div>
                <span className="font-medium">Hash:</span>{' '}
                <code className="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded">
                  {stepModule.content_hash?.substring(0, 8)}
                </code>
              </div>
              <div>
                <span className="font-medium">Updated:</span>{' '}
                {new Date(stepModule.updated_at).toLocaleString()}
              </div>
            </div>
            {stepModule.file_path && (
              <div className="text-gray-500">
                <span className="font-medium">Original:</span> {stepModule.file_path}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
