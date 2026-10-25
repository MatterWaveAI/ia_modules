import { useEffect, useRef, useState } from 'react'

const WS_BASE_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`

export function useExecutionWebSocket(jobId, onUpdate) {
  const ws = useRef(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeout = useRef(null)

  useEffect(() => {
    if (!jobId) return

    const connect = () => {
      const wsUrl = `${WS_BASE_URL}/ws/execution/${jobId}`
      console.log('Connecting to WebSocket:', wsUrl)

      try {
        ws.current = new WebSocket(wsUrl)

        ws.current.onopen = () => {
          console.log('WebSocket connected for execution:', jobId)
          setIsConnected(true)
        }

        ws.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('WebSocket message received:', data)
            if (onUpdate) {
              onUpdate(data)
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }

        ws.current.onerror = (error) => {
          console.warn('Execution WebSocket error (backend may be down)')
          setIsConnected(false)
        }

        ws.current.onclose = () => {
          console.log('WebSocket disconnected for execution:', jobId)
          setIsConnected(false)
          
          // Attempt to reconnect after 5 seconds
          reconnectTimeout.current = setTimeout(() => {
            console.log('Attempting to reconnect WebSocket...')
            connect()
          }, 5000)
        }
      } catch (error) {
        console.warn('Failed to create WebSocket connection:', error)
        setIsConnected(false)
      }
    }

    connect()

    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current)
      }
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [jobId, onUpdate])

  return { isConnected }
}

export function useMetricsWebSocket(onUpdate) {
  const ws = useRef(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeout = useRef(null)

  useEffect(() => {
    const connect = () => {
      const wsUrl = `${WS_BASE_URL}/ws/metrics`
      console.log('Connecting to WebSocket:', wsUrl)

      try {
        ws.current = new WebSocket(wsUrl)

        ws.current.onopen = () => {
          console.log('WebSocket connected for metrics')
          setIsConnected(true)
        }

        ws.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('Metrics WebSocket message received:', data)
            if (onUpdate) {
              onUpdate(data)
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }

        ws.current.onerror = (error) => {
          console.warn('Metrics WebSocket error (backend may be down)')
          setIsConnected(false)
        }

        ws.current.onclose = () => {
          console.log('Metrics WebSocket disconnected')
          setIsConnected(false)
          
          // Attempt to reconnect after 5 seconds
          reconnectTimeout.current = setTimeout(() => {
            console.log('Attempting to reconnect WebSocket...')
            connect()
          }, 5000)
        }
      } catch (error) {
        console.warn('Failed to create WebSocket connection:', error)
        setIsConnected(false)
      }
    }

    connect()

    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current)
      }
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [onUpdate])

  return { isConnected }
}
