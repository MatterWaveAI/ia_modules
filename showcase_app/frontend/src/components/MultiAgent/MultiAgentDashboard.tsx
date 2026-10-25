/**
 * Multi-Agent Dashboard
 * 
 * Main component for visualizing multi-agent workflows with:
 * - Workflow selection and creation
 * - Interactive graph visualization
 * - Real-time communication logs
 * - Agent statistics and performance metrics
 * - Execution controls
 */

import React, { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || '';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Play, RefreshCw, Download, Eye, Activity } from 'lucide-react';
import WorkflowGraph from './WorkflowGraph';
import CommunicationLog from './CommunicationLog';
import AgentStatsPanel from './AgentStatsPanel';
import WorkflowBuilder from './WorkflowBuilder';
import WorkflowTemplates from './WorkflowTemplates';

interface Workflow {
  workflow_id: string;
  status: string;
  agent_count: number;
  edge_count: number;
  created_at: string;
  mermaid_diagram?: string;
}

interface WorkflowState {
  workflow_id: string;
  status: string;
  agent_stats: Record<string, any>;
  current_state: any;
  execution_count: number;
  last_execution: string | null;
}

interface Communication {
  timestamp: string;
  type: string;
  agent: string;
  data: any;
  duration?: number;
}

const MultiAgentDashboard: React.FC = () => {
  // State management
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<string | null>(null);
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null);
  const [communications, setCommunications] = useState<Communication[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [autoRefresh, setAutoRefresh] = useState(false);

  // API base URL
  const MULTI_AGENT_API = `${API_BASE}/api/multi-agent`;

  // Load workflows on mount
  useEffect(() => {
    loadWorkflows();
  }, []);

  // Auto-refresh when executing
  useEffect(() => {
    if (autoRefresh && selectedWorkflow) {
      const interval = setInterval(() => {
        loadWorkflowState(selectedWorkflow);
        loadCommunications(selectedWorkflow);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, selectedWorkflow]);

  // Load all workflows
  const loadWorkflows = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${MULTI_AGENT_API}/workflows`);
      if (!response.ok) throw new Error('Failed to load workflows');
      const data = await response.json();
      setWorkflows(data.workflows || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workflows');
    } finally {
      setIsLoading(false);
    }
  };

  // Load workflow state
  const loadWorkflowState = async (workflowId: string) => {
    try {
      const response = await fetch(`${MULTI_AGENT_API}/workflows/${workflowId}/state`);
      if (!response.ok) throw new Error('Failed to load workflow state');
      const data = await response.json();
      setWorkflowState(data);
    } catch (err) {
      console.error('Failed to load workflow state:', err);
    }
  };

  // Load communications
  const loadCommunications = async (workflowId: string) => {
    try {
      const response = await fetch(`${MULTI_AGENT_API}/workflows/${workflowId}/communications`);
      if (!response.ok) throw new Error('Failed to load communications');
      const data = await response.json();
      setCommunications(data.communications || []);
    } catch (err) {
      console.error('Failed to load communications:', err);
    }
  };

  // Handle workflow selection
  const handleWorkflowSelect = async (workflowId: string) => {
    setSelectedWorkflow(workflowId);
    await loadWorkflowState(workflowId);
    await loadCommunications(workflowId);
  };

  // Execute workflow
  const executeWorkflow = async () => {
    if (!selectedWorkflow) return;

    try {
      setIsExecuting(true);
      setAutoRefresh(true);
      setError(null);

      const response = await fetch(`${MULTI_AGENT_API}/workflows/${selectedWorkflow}/executions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_agent: 'planner', // Default start agent
          initial_data: { task: 'Demo task execution' }
        })
      });

      if (!response.ok) throw new Error('Failed to execute workflow');
      const result = await response.json();

      // Reload state and communications
      await loadWorkflowState(selectedWorkflow);
      await loadCommunications(selectedWorkflow);

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Execution failed');
    } finally {
      setIsExecuting(false);
      setAutoRefresh(false);
    }
  };

  // Create workflow from template
  const handleTemplateSelect = async (template: any) => {
    try {
      setIsLoading(true);
      const workflowId = `workflow_${Date.now()}`;
      
      const response = await fetch(`${MULTI_AGENT_API}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: workflowId,
          agents: template.agents,
          edges: template.edges,
          feedback_loops: template.feedback_loops
        })
      });

      if (!response.ok) throw new Error('Failed to create workflow');
      
      await loadWorkflows();
      setSelectedWorkflow(workflowId);
      setActiveTab('overview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create workflow');
    } finally {
      setIsLoading(false);
    }
  };

  // Export workflow data
  const exportWorkflowData = () => {
    if (!workflowState) return;
    
    const data = {
      workflow: workflowState,
      communications: communications
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow_${selectedWorkflow}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Multi-Agent Orchestration</h1>
          <p className="text-muted-foreground mt-1">
            Visualize and manage multi-agent workflows with real-time tracking
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={loadWorkflows}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {selectedWorkflow && (
            <Button
              onClick={exportWorkflowData}
              variant="outline"
            >
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Workflow Selector */}
      <Card>
        <CardHeader>
          <CardTitle>Workflow Selection</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 items-center">
            <div className="flex-1">
              <Select
                value={selectedWorkflow || ''}
                onValueChange={handleWorkflowSelect}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a workflow..." />
                </SelectTrigger>
                <SelectContent>
                  {workflows.map((workflow) => (
                    <SelectItem key={workflow.workflow_id} value={workflow.workflow_id}>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{workflow.status}</Badge>
                        <span>{workflow.workflow_id}</span>
                        <span className="text-muted-foreground text-sm">
                          ({workflow.agent_count} agents)
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {selectedWorkflow && (
              <Button
                onClick={executeWorkflow}
                disabled={isExecuting}
                size="lg"
              >
                {isExecuting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Execute Workflow
                  </>
                )}
              </Button>
            )}
          </div>
          
          {workflowState && (
            <div className="mt-4 flex gap-4 text-sm">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                <span className="font-medium">Status:</span>
                <Badge>{workflowState.status}</Badge>
              </div>
              <div className="flex items-center gap-2">
                <Eye className="h-4 w-4" />
                <span className="font-medium">Executions:</span>
                <span>{workflowState.execution_count}</span>
              </div>
              {workflowState.last_execution && (
                <div className="flex items-center gap-2">
                  <span className="font-medium">Last Run:</span>
                  <span className="text-muted-foreground">
                    {new Date(workflowState.last_execution).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="graph">Workflow Graph</TabsTrigger>
          <TabsTrigger value="communications">Communications</TabsTrigger>
          <TabsTrigger value="builder">Builder</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {selectedWorkflow ? (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Workflow Visualization</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {workflows.find(w => w.workflow_id === selectedWorkflow)?.mermaid_diagram && (
                      <WorkflowGraph
                        mermaidDiagram={workflows.find(w => w.workflow_id === selectedWorkflow)!.mermaid_diagram!}
                        communications={communications}
                      />
                    )}
                  </CardContent>
                </Card>

                <AgentStatsPanel
                  agentStats={workflowState?.agent_stats || {}}
                  workflowState={workflowState}
                />
              </div>

              <CommunicationLog
                communications={communications}
                isLive={isExecuting}
              />
            </>
          ) : (
            <Card>
              <CardContent className="p-12 text-center">
                <p className="text-muted-foreground">
                  Select a workflow to view details or create a new one from templates
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Graph Tab */}
        <TabsContent value="graph">
          {selectedWorkflow && workflows.find(w => w.workflow_id === selectedWorkflow)?.mermaid_diagram ? (
            <Card>
              <CardHeader>
                <CardTitle>Interactive Workflow Graph</CardTitle>
              </CardHeader>
              <CardContent>
                <WorkflowGraph
                  mermaidDiagram={workflows.find(w => w.workflow_id === selectedWorkflow)!.mermaid_diagram!}
                  communications={communications}
                  interactive={true}
                />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-12 text-center">
                <p className="text-muted-foreground">Select a workflow to view its graph</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Communications Tab */}
        <TabsContent value="communications">
          {selectedWorkflow ? (
            <CommunicationLog
              communications={communications}
              isLive={isExecuting}
              detailed={true}
            />
          ) : (
            <Card>
              <CardContent className="p-12 text-center">
                <p className="text-muted-foreground">
                  Select a workflow to view communication logs
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Builder Tab */}
        <TabsContent value="builder">
          <WorkflowBuilder onWorkflowCreated={loadWorkflows} />
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates">
          <WorkflowTemplates onTemplateSelect={handleTemplateSelect} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MultiAgentDashboard;
