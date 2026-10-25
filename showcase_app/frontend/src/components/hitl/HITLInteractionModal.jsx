import { useState } from 'react';
import { X, Clock, AlertCircle } from 'lucide-react';

export default function HITLInteractionModal({ interaction, onRespond, onCancel, onClose }) {
  const [formData, setFormData] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFieldChange = (fieldName, value) => {
    setFormData(prev => ({
      ...prev,
      [fieldName]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      await onRespond(interaction.interaction_id, formData);
      onClose();
    } catch (error) {
      alert(`Error submitting response: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (confirm('Are you sure you want to cancel this interaction?')) {
      await onCancel(interaction.interaction_id);
      onClose();
    }
  };

  const renderField = (field) => {
    const value = formData[field.name] || field.default || '';

    switch (field.type) {
      case 'text':
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            required={field.required}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        );

      case 'textarea':
        return (
          <textarea
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder}
            required={field.required}
            rows={field.rows || 4}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
          />
        );

      case 'radio':
        return (
          <div className="space-y-2">
            {field.options.map((option) => {
              const optionValue = typeof option === 'object' ? option.value : option;
              const optionLabel = typeof option === 'object' ? option.label : option;

              return (
                <label key={optionValue} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name={field.name}
                    value={optionValue}
                    checked={value === optionValue}
                    onChange={(e) => handleFieldChange(field.name, e.target.value)}
                    required={field.required}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">{optionLabel}</span>
                </label>
              );
            })}
          </div>
        );

      case 'select':
        return (
          <select
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            required={field.required}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select...</option>
            {field.options.map((option) => {
              const optionValue = typeof option === 'object' ? option.value : option;
              const optionLabel = typeof option === 'object' ? option.label : option;

              return (
                <option key={optionValue} value={optionValue}>
                  {optionLabel}
                </option>
              );
            })}
          </select>
        );

      case 'checkbox':
        return (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={!!value}
              onChange={(e) => handleFieldChange(field.name, e.target.checked)}
              required={field.required}
              className="w-4 h-4 text-blue-600 rounded"
            />
            <span className="text-sm">{field.label}</span>
          </label>
        );

      case 'number':
        return (
          <input
            type="number"
            value={value}
            onChange={(e) => handleFieldChange(field.name, parseFloat(e.target.value))}
            placeholder={field.placeholder}
            required={field.required}
            min={field.min}
            max={field.max}
            step={field.step}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        );

      default:
        return (
          <input
            type="text"
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        );
    }
  };

  const getTimeRemaining = () => {
    if (!interaction.expires_at) return null;

    const now = new Date();
    const expires = new Date(interaction.expires_at);
    const diff = expires - now;

    if (diff <= 0) return 'Expired';

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 0) {
      return `${hours}h ${minutes}m remaining`;
    }
    return `${minutes}m remaining`;
  };

  const timeRemaining = getTimeRemaining();
  const isExpired = timeRemaining === 'Expired';

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Human Input Required</h2>
            <p className="text-sm text-gray-500 mt-1">Step: {interaction.step_name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X size={24} />
          </button>
        </div>

        {/* Status Bar */}
        <div className="px-6 py-3 bg-yellow-50 border-b border-yellow-100 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-yellow-800">
            <AlertCircle size={16} />
            <span>Pipeline execution is paused</span>
          </div>
          {timeRemaining && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Clock size={16} />
              <span className={isExpired ? 'text-red-600 font-semibold' : ''}>
                {timeRemaining}
              </span>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Prompt */}
          <div className="mb-6">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Prompt</h3>
            <p className="text-gray-700 dark:text-gray-300">{interaction.prompt}</p>
          </div>

          {/* Context Data */}
          {interaction.context_data && Object.keys(interaction.context_data).length > 0 && (
            <div className="mb-6">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Context</h3>
              <div className="bg-gray-50 dark:bg-gray-800/50 border dark:border-gray-700 rounded-lg p-4">
                <pre className="text-xs text-gray-700 dark:text-gray-300 overflow-x-auto">
                  {JSON.stringify(interaction.context_data, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} id="hitl-form">
            <div className="space-y-4">
              {interaction.ui_schema?.fields?.map((field) => (
                <div key={field.name}>
                  {field.type !== 'checkbox' && (
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      {field.label || field.name}
                      {field.required && <span className="text-red-500 ml-1">*</span>}
                    </label>
                  )}
                  {renderField(field)}
                  {field.description && (
                    <p className="text-xs text-gray-500 mt-1">{field.description}</p>
                  )}
                </div>
              ))}
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="p-6 border-t bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between">
          <button
            type="button"
            onClick={handleCancel}
            className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100"
          >
            Cancel Interaction
          </button>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              Close
            </button>
            <button
              type="submit"
              form="hitl-form"
              disabled={isSubmitting || isExpired}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Submitting...' : 'Submit Response'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
