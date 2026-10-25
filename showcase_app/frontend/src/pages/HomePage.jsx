import React from 'react'
import { Link } from 'react-router-dom'
import { Play, BarChart3, CheckCircle, Clock, TrendingUp, Shield } from 'lucide-react'

export default function HomePage() {
  return (
    <div className="space-y-8 max-w-6xl">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gray-950 p-8 lg:p-10 text-white">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-600/20 via-transparent to-accent-500/10"></div>
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold tracking-tight mb-3">Welcome to IA Modules Showcase</h1>
          <p className="text-base lg:text-lg text-gray-300 mb-8 max-w-2xl">
            Production-ready AI agent framework with enterprise-grade reliability and observability
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/pipelines"
              className="bg-white text-gray-900 px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-gray-100 transition-colors"
            >
              Try Example Pipelines
            </Link>
            <Link
              to="/metrics"
              className="border border-white/20 bg-white/10 px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-white/20 transition-colors"
            >
              View Metrics Dashboard
            </Link>
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div>
        <h2 className="section-heading mb-5">Key Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <FeatureCard
            icon={<Play className="text-primary-500" size={32} />}
            title="Graph-Based Pipelines"
            description="Define complex workflows as directed graphs with conditional routing and parallel execution"
          />
          <FeatureCard
            icon={<BarChart3 className="text-primary-500" size={32} />}
            title="12 Reliability Metrics"
            description="Track SVR, CR, PC, HIR, MA, MTTE, RSR, EQS, TCL, WCT, TPW, CPSW with real-time monitoring"
          />
          <FeatureCard
            icon={<Shield className="text-primary-500" size={32} />}
            title="EARF Three Pillars"
            description="Total Observability, Absolute Reproducibility, Formal Safety & Verification"
          />
          <FeatureCard
            icon={<CheckCircle className="text-primary-500" size={32} />}
            title="Human-in-the-Loop"
            description="Pause-and-resume workflows with human approval gates and collaborative decision making"
          />
          <FeatureCard
            icon={<Clock className="text-primary-500" size={32} />}
            title="Checkpointing & Resume"
            description="Automatic state snapshots enable resuming failed pipelines from last successful step"
          />
          <FeatureCard
            icon={<TrendingUp className="text-primary-500" size={32} />}
            title="Memory & Conversation"
            description="Context-aware processing with conversation history and session management"
          />
          <FeatureCard
            icon={<Play className="text-primary-500" size={32} />}
            title="Advanced Routing"
            description="Conditional branching, parallel execution, and loop detection for complex workflows"
          />
        </div>
      </div>

      {/* Stats */}
      <div>
        <h2 className="section-heading mb-5">Framework Capabilities</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Example Pipelines" value="9" color="blue" />
          <StatCard label="Reliability Metrics" value="12" color="purple" />
          <StatCard label="EARF Pillars" value="3" color="green" />
          <StatCard label="Python Support" value="3.9-3.13" color="blue" />
        </div>
      </div>

      {/* Quick Start */}
      <div className="card p-6 lg:p-8">
        <h2 className="section-heading mb-5">Quick Start</h2>
        <div className="space-y-4">
          <QuickStartStep
            number="1"
            title="Explore Example Pipelines"
            description="Navigate to Pipelines to see pre-built examples demonstrating framework capabilities"
          />
          <QuickStartStep
            number="2"
            title="Run a Pipeline"
            description="Click 'Execute' on any pipeline to see real-time execution with live metrics tracking"
          />
          <QuickStartStep
            number="3"
            title="Monitor Reliability"
            description="View the Metrics Dashboard to see comprehensive reliability metrics and SLO compliance"
          />
          <QuickStartStep
            number="4"
            title="Review Execution History"
            description="Check Executions tab to see all pipeline runs with detailed logs and results"
          />
        </div>
      </div>

      {/* Documentation Links */}
      <div className="card p-6 lg:p-8 bg-gray-50 dark:bg-gray-900/50">
        <h2 className="section-heading mb-5">Documentation</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <DocLink
            title="Getting Started"
            description="Quick start guide and installation"
            href="/docs/GETTING_STARTED.md"
          />
          <DocLink
            title="API Reference"
            description="Complete API documentation"
            href="/docs/API_REFERENCE.md"
          />
          <DocLink
            title="Reliability Guide"
            description="EARF compliance and monitoring"
            href="/docs/RELIABILITY_USAGE_GUIDE.md"
          />
          <DocLink
            title="Features Overview"
            description="Complete feature matrix"
            href="/docs/FEATURES.md"
          />
        </div>
      </div>
    </div>
  )
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="card p-5 hover:shadow-soft-md transition-shadow">
      <div className="mb-3">{icon}</div>
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1.5">{title}</h3>
      <p className="text-gray-500 dark:text-gray-400 text-[13px] leading-relaxed">{description}</p>
    </div>
  )
}

function StatCard({ label, value, color }) {
  const dotColors = {
    green: 'bg-emerald-500',
    blue: 'bg-primary-500',
    purple: 'bg-purple-500',
  }

  return (
    <div className="card p-5">
      <div className="flex items-center space-x-2 mb-3">
        <div className={`w-2 h-2 rounded-full ${dotColors[color]}`}></div>
        <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</div>
      </div>
      <div className="text-2xl font-bold text-gray-900 dark:text-white">{value}</div>
    </div>
  )
}

function QuickStartStep({ number, title, description }) {
  return (
    <div className="flex items-start space-x-4">
      <div className="bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 rounded-lg w-7 h-7 flex items-center justify-center text-xs font-semibold flex-shrink-0 mt-0.5">
        {number}
      </div>
      <div>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h3>
        <p className="text-gray-500 dark:text-gray-400 text-[13px] mt-0.5">{description}</p>
      </div>
    </div>
  )
}

function DocLink({ title, description, href }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white dark:bg-gray-800/50 rounded-xl p-4 border border-gray-200/40 dark:border-gray-700/40 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
    >
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-0.5">{title}</h3>
      <p className="text-gray-500 dark:text-gray-400 text-[13px]">{description}</p>
    </a>
  )
}
