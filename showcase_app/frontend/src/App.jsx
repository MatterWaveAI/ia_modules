import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate, useLocation } from 'react-router-dom'
import { Home, BarChart3, Play, FileCode, Github, Edit, Sparkles, Network, Moon, Sun, HelpCircle, Menu, X, Database, Globe, Users, Cpu, Puzzle, Share2, Shield } from 'lucide-react'
import { Toaster } from 'react-hot-toast'
import axios from 'axios'
import HomePage from './pages/HomePage'
import PipelinesPage from './pages/PipelinesPage'
import MetricsPage from './pages/MetricsPage'
import ExecutionsPage from './pages/ExecutionsPage'
import ExecutionDetailPage from './pages/ExecutionDetailPage'
import PipelineEditorPage from './pages/PipelineEditorPage'
import PatternsPage from './pages/PatternsPage'
import WebScrapingPage from './pages/WebScrapingPage'
import MultiAgentDashboard from './components/MultiAgent/MultiAgentDashboard'
import AgentDashboard from './pages/AgentDashboard'
import AgentExecutionsPage from './pages/AgentExecutionsPage'
import LLMDashboard from './pages/LLMDashboard'
import CollaborationPage from './pages/CollaborationPage'
import PluginsPage from './pages/PluginsPage'
import GuardrailsPage from './pages/GuardrailsPage'
import ErrorBoundary from './components/ErrorBoundary/ErrorBoundary'
import ThemeProvider, { useTheme } from './components/ThemeProvider/ThemeProvider'
import KeyboardShortcutsModal from './components/ui/keyboard-shortcuts-modal'
import useKeyboardShortcuts from './hooks/useKeyboardShortcuts'

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [shortcutsModalOpen, setShortcutsModalOpen] = useState(false)
  const [backendStatus, setBackendStatus] = useState({
    connected: false,
    database: 'checking...',
    websocket: false
  })
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()

  // Check backend status
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || ''
        const response = await axios.get(`${apiUrl}/health`, {
          timeout: 5000,
          headers: { 'Accept': 'application/json' }
        })
        setBackendStatus({
          connected: true,
          database: response.data.database || 'unknown',
          websocket: false
        })
      } catch (error) {
        console.error('Backend health check failed:', error.message)
        setBackendStatus({
          connected: false,
          database: 'disconnected',
          websocket: false
        })
      }
    }

    checkBackend()
    const interval = setInterval(checkBackend, 30000)
    return () => clearInterval(interval)
  }, [])

  // WebSocket connection for real-time updates
  useEffect(() => {
    if (!backendStatus.connected) return

    const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`
    const ws = new WebSocket(`${wsUrl}/ws/metrics`)

    ws.onopen = () => {
      console.log('WebSocket connected')
      setBackendStatus(prev => ({ ...prev, websocket: true }))
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setBackendStatus(prev => ({ ...prev, websocket: false }))
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setBackendStatus(prev => ({ ...prev, websocket: false }))
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [backendStatus.connected])

  // Keyboard shortcuts
  useKeyboardShortcuts({
    'cmd+/': () => setShortcutsModalOpen(true),
    'cmd+b': () => setSidebarOpen(prev => !prev),
    'cmd+d': () => toggleTheme(),
    'esc': () => {
      setShortcutsModalOpen(false)
      setMobileMenuOpen(false)
    },
  })

  const shortcuts = {
    'Navigation': [
      { keys: 'cmd+/', description: 'Show keyboard shortcuts' },
      { keys: 'cmd+b', description: 'Toggle sidebar' },
      { keys: 'esc', description: 'Close modals' },
    ],
    'Appearance': [
      { keys: 'cmd+d', description: 'Toggle dark mode' },
    ],
  }

  return (
    <div className="flex h-screen bg-gray-50/80 dark:bg-gray-950">
      {/* Mobile Menu Button */}
      <button
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2.5 bg-gradient-to-br from-primary-600 to-accent-600 text-white rounded-xl shadow-lg shadow-primary-500/25 hover:shadow-primary-500/40 transition-all"
      >
        {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* Mobile Menu Backdrop */}
      {mobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        bg-gray-950 text-white
        ${sidebarOpen ? 'w-64' : 'w-20'}
        transition-all duration-300 flex flex-col
        fixed lg:relative inset-y-0 left-0 z-40
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        border-r border-gray-800/50
      `}>
        {/* Logo Section */}
        <div className="p-5 border-b border-white/[0.06]">
          <div className="flex items-center space-x-3">
            <div className="bg-primary-600 rounded-xl p-2">
              <FileCode size={22} className="text-white" />
            </div>
            {sidebarOpen && (
              <div>
                <h1 className="font-semibold text-[15px] text-white tracking-tight">IA Modules</h1>
                <p className="text-[11px] text-gray-500 font-medium">Showcase v0.0.3</p>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          <NavLink to="/" icon={<Home size={20} />} text="Home" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/pipelines" icon={<FileCode size={20} />} text="Pipelines" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/editor" icon={<Edit size={20} />} text="Editor" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/executions" icon={<Play size={20} />} text="Executions" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/patterns" icon={<Sparkles size={20} />} text="Patterns" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/web-scraping" icon={<Globe size={20} />} text="Web Scraping" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/multi-agent" icon={<Network size={20} />} text="Multi-Agent" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/collaboration" icon={<Share2 size={20} />} text="Collaboration" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/guardrails" icon={<Shield size={20} />} text="Guardrails" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/metrics" icon={<BarChart3 size={20} />} text="Metrics" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/agents" icon={<Users size={20} />} text="Agents" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/plugins" icon={<Puzzle size={20} />} text="Plugins" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
          <NavLink to="/llm" icon={<Cpu size={20} />} text="LLM Usage" sidebarOpen={sidebarOpen} onClick={() => setMobileMenuOpen(false)} />
        </nav>

        {/* Footer Actions */}
        <div className="px-3 py-4 border-t border-white/[0.06] space-y-0.5">
          <button
            onClick={() => setShortcutsModalOpen(true)}
            className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg hover:bg-white/[0.06] transition text-gray-500 hover:text-gray-300 group"
          >
            <HelpCircle size={18} className="group-hover:text-gray-300 transition" />
            {sidebarOpen && <span className="text-[13px] font-medium">Shortcuts</span>}
          </button>
          <a
            href="https://github.com/yourusername/ia_modules"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-3 px-3 py-2.5 rounded-lg hover:bg-white/[0.06] transition text-gray-500 hover:text-gray-300 group"
          >
            <Github size={18} className="group-hover:text-gray-300 transition" />
            {sidebarOpen && <span className="text-[13px] font-medium">GitHub</span>}
          </a>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl px-4 lg:px-8 py-4 flex items-center justify-between border-b border-gray-200/50 dark:border-gray-800/50">
          <div className="ml-12 lg:ml-0">
            <h2 className="text-lg lg:text-xl font-semibold text-gray-900 dark:text-white tracking-tight">IA Modules Showcase</h2>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Production-ready AI agent framework</p>
          </div>
          <div className="flex items-center space-x-3">
            <div className="hidden sm:flex items-center space-x-4 text-sm">
              {/* Database Status */}
              <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-gray-100/80 dark:bg-gray-800/40 border border-gray-200/40 dark:border-gray-700/40">
                <div className={`w-2 h-2 rounded-full ${backendStatus.connected ? 'bg-success-500 animate-pulse' : 'bg-error-500'}`}></div>
                <Database size={14} className="text-gray-500 dark:text-gray-400" />
                <span className="text-gray-600 dark:text-gray-400 font-medium">
                  {backendStatus.connected ? backendStatus.database : 'Disconnected'}
                </span>
              </div>

              {/* WebSocket Status */}
              {backendStatus.connected && (
                <div className="flex items-center space-x-2 pl-4 border-l border-gray-200 dark:border-gray-700">
                  <div className={`w-2 h-2 rounded-full ${backendStatus.websocket ? 'bg-primary-500 animate-pulse-glow' : 'bg-gray-400'}`}></div>
                  <span className="text-gray-600 dark:text-gray-400 font-medium">
                    WS {backendStatus.websocket ? 'Connected' : 'Offline'}
                  </span>
                </div>
              )}
            </div>
            <button
              onClick={toggleTheme}
              className="p-2.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition group"
              aria-label="Toggle dark mode"
            >
              {theme === 'light' ? (
                <Moon size={20} className="text-gray-500 group-hover:text-primary-600 transition" />
              ) : (
                <Sun size={20} className="text-gray-400 group-hover:text-warning-500 transition" />
              )}
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-4 lg:p-8">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/pipelines" element={<PipelinesPage />} />
            <Route path="/editor" element={<PipelineEditorPage />} />
            <Route path="/editor/:pipelineId" element={<PipelineEditorPage />} />
            <Route path="/executions" element={<ExecutionsPage />} />
            <Route path="/executions/:jobId" element={<ExecutionDetailPage />} />
            <Route path="/patterns" element={<PatternsPage />} />
            <Route path="/patterns/:patternId" element={<PatternsPage />} />
            <Route path="/web-scraping" element={<WebScrapingPage />} />
            <Route path="/multi-agent" element={<MultiAgentDashboard />} />
            <Route path="/collaboration" element={<CollaborationPage />} />
            <Route path="/collaboration/:patternId" element={<CollaborationPage />} />
            <Route path="/guardrails" element={<GuardrailsPage />} />
            <Route path="/metrics" element={<MetricsPage />} />
            <Route path="/agents" element={<AgentDashboard />} />
            <Route path="/agents/executions" element={<AgentExecutionsPage />} />
            <Route path="/plugins" element={<PluginsPage />} />
            <Route path="/llm" element={<LLMDashboard />} />
          </Routes>
        </main>
      </div>

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal
        isOpen={shortcutsModalOpen}
        onClose={() => setShortcutsModalOpen(false)}
        shortcuts={shortcuts}
      />

      {/* Toast Notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: theme === 'dark' ? '#1f2937' : '#fff',
            color: theme === 'dark' ? '#f9fafb' : '#111827',
            border: `1px solid ${theme === 'dark' ? '#374151' : '#e5e7eb'}`,
            borderRadius: '12px',
            boxShadow: '0 10px 40px rgba(0, 0, 0, 0.15)',
          },
          success: {
            iconTheme: {
              primary: '#22c55e',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />
    </div>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="light">
        <BrowserRouter>
          <AppContent />
        </BrowserRouter>
      </ThemeProvider>
    </ErrorBoundary>
  )
}

function NavLink({ to, icon, text, sidebarOpen, onClick }) {
  const location = useLocation()
  const isActive = location.pathname === to || (to !== '/' && location.pathname.startsWith(to))

  return (
    <Link
      to={to}
      onClick={onClick}
      className={`
        flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors text-[13px] font-medium group
        ${isActive
          ? 'bg-white/[0.1] text-white'
          : 'hover:bg-white/[0.06] text-gray-400 hover:text-gray-200'
        }
      `}
    >
      <div className={`flex-shrink-0 ${isActive ? 'text-primary-400' : 'text-gray-500 group-hover:text-gray-300'}`}>{icon}</div>
      {sidebarOpen && <span>{text}</span>}
    </Link>
  )
}

export default App
