/**
 * Workflow Builder Component
 * 
 * Visual interface for creating custom multi-agent workflows
 * with drag-and-drop agent placement, edge connections, and configuration
 */

import React, { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || '';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Plus, Trash2, Link2, Save } from 'lucide-react';

interface Agent {
  id: string;
  role: string;
  description: string;
}

interface Edge {
  from: string;
  to: string;
  condition?: string;
}

interface WorkflowBuilderProps {
  onWorkflowCreated: () => void;
}

const WorkflowBuilder: React.FC<WorkflowBuilderProps> = ({ onWorkflowCreated }) => {
  const [workflowId, setWorkflowId] = useState('');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Available agent roles
  const agentRoles = [
    'planner',
    'researcher',
    'coder',
    'critic',
    'analyzer',
    'generator',
    'validator',
    'coordinator'
  ];

  // Add new agent
  const addAgent = () => {
    setAgents([
      ...agents,
      { id: `agent_${Date.now()}`, role: 'planner', description: '' }
    ]);
  };

  // Remove agent
  const removeAgent = (id: string) => {
    setAgents(agents.filter(a => a.id !== id));
    // Also remove edges connected to this agent
    setEdges(edges.filter(e => e.from !== id && e.to !== id));
  };

  // Update agent
  const updateAgent = (id: string, field: keyof Agent, value: string) => {
    setAgents(agents.map(a => 
      a.id === id ? { ...a, [field]: value } : a
    ));
  };

  // Add edge
  const addEdge = () => {
    if (agents.length >= 2) {
      setEdges([
        ...edges,
        { from: agents[0].id, to: agents[1].id }
      ]);
    }
  };

  // Remove edge
  const removeEdge = (index: number) => {
    setEdges(edges.filter((_, i) => i !== index));
  };

  // Update edge
  const updateEdge = (index: number, field: keyof Edge, value: string) => {
    setEdges(edges.map((e, i) => 
      i === index ? { ...e, [field]: value } : e
    ));
  };

  // Create workflow
  const createWorkflow = async () => {
    if (!workflowId.trim()) {
      setError('Workflow ID is required');
      return;
    }

    if (agents.length === 0) {
      setError('At least one agent is required');
      return;
    }

    try {
      setError(null);
      const response = await fetch(`${API_BASE}/api/multi-agent/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: workflowId,
          agents,
          edges
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create workflow');
      }

      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onWorkflowCreated();
      }, 2000);

      // Reset form
      setWorkflowId('');
      setAgents([]);
      setEdges([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create workflow');
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create Custom Workflow</CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Workflow ID */}
        <div className="space-y-2">
          <Label htmlFor="workflow-id">Workflow ID</Label>
          <Input
            id="workflow-id"
            placeholder="my_custom_workflow"
            value={workflowId}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setWorkflowId(e.target.value)}
          />
        </div>

        {/* Agents Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Agents</Label>
            <Button onClick={addAgent} size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add Agent
            </Button>
          </div>

          <div className="space-y-3">
            {agents.map((agent) => (
              <div key={agent.id} className="border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">Agent {agent.id.split('_')[1]}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeAgent(agent.id)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>ID</Label>
                    <Input
                      value={agent.id}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'id', e.target.value)}
                      placeholder="agent_id"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Role</Label>
                    <Select
                      value={agent.role}
                      onValueChange={(value) => updateAgent(agent.id, 'role', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {agentRoles.map(role => (
                          <SelectItem key={role} value={role}>
                            {role}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input
                    value={agent.description}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAgent(agent.id, 'description', e.target.value)}
                    placeholder="What does this agent do?"
                  />
                </div>
              </div>
            ))}

            {agents.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No agents yet. Click "Add Agent" to start building your workflow.
              </div>
            )}
          </div>
        </div>

        {/* Edges Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Connections</Label>
            <Button 
              onClick={addEdge} 
              size="sm"
              disabled={agents.length < 2}
            >
              <Link2 className="h-4 w-4 mr-2" />
              Add Connection
            </Button>
          </div>

          <div className="space-y-3">
            {edges.map((edge, index) => (
              <div key={index} className="border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">Connection {index + 1}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeEdge(index)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-2">
                    <Label>From</Label>
                    <Select
                      value={edge.from}
                      onValueChange={(value) => updateEdge(index, 'from', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {agents.map(agent => (
                          <SelectItem key={agent.id} value={agent.id}>
                            {agent.id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>To</Label>
                    <Select
                      value={edge.to}
                      onValueChange={(value) => updateEdge(index, 'to', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {agents.map(agent => (
                          <SelectItem key={agent.id} value={agent.id}>
                            {agent.id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Condition (optional)</Label>
                    <Input
                      value={edge.condition || ''}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateEdge(index, 'condition', e.target.value)}
                      placeholder="condition_name"
                    />
                  </div>
                </div>
              </div>
            ))}

            {edges.length === 0 && agents.length >= 2 && (
              <div className="text-center py-8 text-muted-foreground">
                No connections yet. Click "Add Connection" to link agents together.
              </div>
            )}
          </div>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert>
            <AlertDescription>Workflow created successfully!</AlertDescription>
          </Alert>
        )}

        {/* Create Button */}
        <Button 
          onClick={createWorkflow}
          className="w-full"
          size="lg"
          disabled={!workflowId || agents.length === 0}
        >
          <Save className="h-4 w-4 mr-2" />
          Create Workflow
        </Button>
      </CardContent>
    </Card>
  );
};

export default WorkflowBuilder;
