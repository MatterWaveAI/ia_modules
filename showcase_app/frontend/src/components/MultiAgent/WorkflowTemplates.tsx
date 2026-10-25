/**
 * Workflow Templates Component
 * 
 * Displays pre-built workflow templates that users can select
 * to quickly create common multi-agent patterns
 */

import React, { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || '';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  GitBranch, 
  RefreshCw, 
  Users, 
  Workflow,
  ArrowRight
} from 'lucide-react';

interface Template {
  name: string;
  description: string;
  agents: any[];
  edges: any[];
  feedback_loops?: any[];
}

interface WorkflowTemplatesProps {
  onTemplateSelect: (template: Template) => void;
}

const WorkflowTemplates: React.FC<WorkflowTemplatesProps> = ({ onTemplateSelect }) => {
  const [templates, setTemplates] = useState<Record<string, Template>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load templates
  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`${API_BASE}/api/multi-agent/templates`);
      if (!response.ok) throw new Error('Failed to load templates');
      const data = await response.json();
      setTemplates(data.templates);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates');
    } finally {
      setIsLoading(false);
    }
  };

  // Get icon for template type
  const getTemplateIcon = (key: string) => {
    switch (key) {
      case 'simple_sequence':
        return <ArrowRight className="h-5 w-5" />;
      case 'feedback_loop':
        return <RefreshCw className="h-5 w-5" />;
      case 'conditional_routing':
        return <GitBranch className="h-5 w-5" />;
      case 'complex_workflow':
        return <Workflow className="h-5 w-5" />;
      default:
        return <Users className="h-5 w-5" />;
    }
  };

  // Get color for template type
  const getTemplateColor = (key: string) => {
    switch (key) {
      case 'simple_sequence':
        return 'bg-blue-500/10 text-blue-600 dark:text-blue-400';
      case 'feedback_loop':
        return 'bg-green-500/10 text-green-600 dark:text-green-400';
      case 'conditional_routing':
        return 'bg-purple-500/10 text-purple-600 dark:text-purple-400';
      case 'complex_workflow':
        return 'bg-orange-500/10 text-orange-600 dark:text-orange-400';
      default:
        return 'bg-gray-500/10 text-gray-600 dark:text-gray-400';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <div className="text-muted-foreground">Loading templates...</div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <div className="text-destructive mb-2">Failed to load templates</div>
          <div className="text-sm text-muted-foreground">{error}</div>
          <Button onClick={loadTemplates} className="mt-4">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold mb-2">Workflow Templates</h2>
        <p className="text-muted-foreground">
          Choose a pre-built template to quickly create common multi-agent patterns
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(templates).map(([key, template]) => (
          <Card key={key} className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className={`p-3 rounded-lg ${getTemplateColor(key)}`}>
                  {getTemplateIcon(key)}
                </div>
                <Badge variant="outline">
                  {template.agents.length} agents
                </Badge>
              </div>
              <CardTitle className="mt-4">{template.name}</CardTitle>
              <CardDescription>{template.description}</CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Agent List */}
              <div>
                <div className="text-sm font-medium mb-2">Agents:</div>
                <div className="flex flex-wrap gap-2">
                  {template.agents.map((agent, idx) => (
                    <Badge key={idx} variant="secondary">
                      {agent.role}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Connections */}
              <div>
                <div className="text-sm font-medium mb-2">Connections:</div>
                <div className="space-y-1 text-sm text-muted-foreground">
                  {template.edges.slice(0, 3).map((edge, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span>{edge.from}</span>
                      <ArrowRight className="h-3 w-3" />
                      <span>{edge.to}</span>
                      {edge.condition && (
                        <Badge variant="outline" className="text-xs">
                          {edge.condition}
                        </Badge>
                      )}
                    </div>
                  ))}
                  {template.edges.length > 3 && (
                    <div className="text-xs">
                      +{template.edges.length - 3} more
                    </div>
                  )}
                </div>
              </div>

              {/* Feedback Loops */}
              {template.feedback_loops && template.feedback_loops.length > 0 && (
                <div>
                  <div className="text-sm font-medium mb-2">Features:</div>
                  <div className="flex items-center gap-2">
                    <RefreshCw className="h-4 w-4 text-green-500" />
                    <span className="text-sm text-muted-foreground">
                      Includes feedback loops
                    </span>
                  </div>
                </div>
              )}

              <Button 
                onClick={() => onTemplateSelect(template)}
                className="w-full"
              >
                Use This Template
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default WorkflowTemplates;
