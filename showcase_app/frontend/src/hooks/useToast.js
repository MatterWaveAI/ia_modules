import toast from 'react-hot-toast'

/**
 * Custom hook for toast notifications with consistent styling
 */
export const useToast = () => {
  const success = (message, options = {}) => {
    return toast.success(message, {
      ...options,
    })
  }

  const error = (message, options = {}) => {
    return toast.error(message, {
      ...options,
    })
  }

  const loading = (message, options = {}) => {
    return toast.loading(message, {
      ...options,
    })
  }

  const promise = (promise, messages, options = {}) => {
    return toast.promise(
      promise,
      {
        loading: messages.loading || 'Loading...',
        success: messages.success || 'Success!',
        error: messages.error || 'Something went wrong',
      },
      options
    )
  }

  const custom = (message, options = {}) => {
    return toast(message, {
      ...options,
    })
  }

  const dismiss = (toastId) => {
    toast.dismiss(toastId)
  }

  return {
    success,
    error,
    loading,
    promise,
    custom,
    dismiss,
  }
}

export default useToast
