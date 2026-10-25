/**
 * Agent Statistics Panel
 * 
 * Displays performance metrics and statistics for agents
 * in the workflow, including execution counts, durations, and iterations
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  TrendingUp, 
  Clock, 
  Repeat, 
  BarChart3,
  Activity
} from 'lucide-react';

interface AgentStats {
  executions: number;
  total_duration: number;
  average_duration?: number;
  iterations?: number[];
}

interface WorkflowState {
  workflow_id: string;
  status: string;
  execution_count: number;
  last_execution: string | null;
}

interface AgentStatsPanelProps {
  agentStats: Record<string, AgentStats>;
  workflowState: WorkflowState | null;
}

const AgentStatsPanel: React.FC<AgentStatsPanelProps> = ({
  agentStats,
  workflowState
}) => {
  // Calculate total executions across all agents
  const totalExecutions = Object.values(agentStats).reduce(
    (sum, stats) => sum + stats.executions, 
    0
  );

  // Find most active agent
  const mostActiveAgent = Object.entries(agentStats).reduce(
    (max, [agent, stats]) => 
      stats.executions > (max.stats?.executions || 0) 
        ? { agent, stats } 
        : max,
    { agent: null as string | null, stats: null as AgentStats | null }
  );

  // Calculate average duration across all agents
  const avgDuration = totalExecutions > 0
    ? Object.values(agentStats).reduce((sum, stats) => sum + stats.total_duration, 0) / totalExecutions
    : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5" />
          Agent Statistics
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-primary/10 rounded-lg p-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <Activity className="h-4 w-4" />
              Total Executions
            </div>
            <div className="text-2xl font-bold">{totalExecutions}</div>
          </div>
          
          <div className="bg-secondary/10 rounded-lg p-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <Clock className="h-4 w-4" />
              Avg Duration
            </div>
            <div className="text-2xl font-bold">
              {avgDuration.toFixed(2)}s
            </div>
          </div>
        </div>

        {/* Most Active Agent */}
        {mostActiveAgent.agent && (
          <div className="border rounded-lg p-3 bg-accent/20">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Most Active Agent</span>
              <Badge variant="default">{mostActiveAgent.agent}</Badge>
            </div>
            <div className="text-2xl font-bold">
              {mostActiveAgent.stats!.executions} executions
            </div>
          </div>
        )}

        {/* Individual Agent Stats */}
        {Object.keys(agentStats).length > 0 ? (
          <div className="space-y-3">
            <div className="text-sm font-medium">Agent Performance</div>
            
            {Object.entries(agentStats).map(([agent, stats]) => {
              const percentage = totalExecutions > 0 
                ? (stats.executions / totalExecutions) * 100 
                : 0;
              
              return (
                <div key={agent} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{agent}</span>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        {stats.executions}x
                      </Badge>
                      <span className="text-muted-foreground">
                        {stats.total_duration.toFixed(2)}s
                      </span>
                    </div>
                  </div>
                  
                  <Progress value={percentage} className="h-2" />
                  
                  {/* Additional Details */}
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    {stats.average_duration && (
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Avg: {stats.average_duration.toFixed(2)}s
                      </div>
                    )}
                    
                    {stats.iterations && stats.iterations.length > 0 && (
                      <div className="flex items-center gap-1">
                        <Repeat className="h-3 w-3" />
                        {stats.iterations.length} iterations
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-6 text-muted-foreground text-sm">
            No agent statistics available yet.
            <br />
            Execute the workflow to generate stats.
          </div>
        )}

        {/* Workflow Status */}
        {workflowState && (
          <div className="border-t pt-4 mt-4">
            <div className="text-sm font-medium mb-3">Workflow Status</div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status:</span>
                <Badge>{workflowState.status}</Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Runs:</span>
                <span className="font-medium">{workflowState.execution_count}</span>
              </div>
              {workflowState.last_execution && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Last Run:</span>
                  <span className="font-medium">
                    {new Date(workflowState.last_execution).toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AgentStatsPanel;
