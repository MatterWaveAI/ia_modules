/**
 * Workflow Graph Component
 * 
 * Renders multi-agent workflows as interactive Mermaid diagrams
 * with real-time highlighting of active agents and communication paths
 */

import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

interface Communication {
  timestamp: string;
  type: string;
  agent: string;
  data: any;
  duration?: number;
}

interface WorkflowGraphProps {
  mermaidDiagram: string;
  communications?: Communication[];
  interactive?: boolean;
}

const WorkflowGraph: React.FC<WorkflowGraphProps> = ({
  mermaidDiagram,
  communications = [],
  interactive = false
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);

  // Initialize Mermaid
  useEffect(() => {
    mermaid.initialize({
      startOnLoad: true,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: {
        useMaxWidth: true,
        htmlLabels: true,
        curve: 'basis'
      }
    });
  }, []);

  // Render diagram
  useEffect(() => {
    if (!containerRef.current || !mermaidDiagram) return;

    const renderDiagram = async () => {
      try {
        setError(null);
        const id = `mermaid-${Date.now()}`;
        const { svg } = await mermaid.render(id, mermaidDiagram);
        
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          
          // Add click handlers if interactive
          if (interactive) {
            const nodes = containerRef.current.querySelectorAll('.node');
            nodes.forEach(node => {
              node.addEventListener('click', (e) => {
                const rect = node.querySelector('rect');
                if (rect) {
                  const agentId = rect.getAttribute('id')?.split('-')[0];
                  if (agentId) {
                    setActiveAgent(agentId);
                  }
                }
              });
            });
          }
        }
      } catch (err) {
        console.error('Mermaid rendering error:', err);
        setError(err instanceof Error ? err.message : 'Failed to render diagram');
      }
    };

    renderDiagram();
  }, [mermaidDiagram, interactive]);

  // Highlight active agents based on communications
  useEffect(() => {
    if (!containerRef.current || !communications.length) return;

    // Get the most recent agent that was activated
    const recentComms = communications.slice(-5);
    const activatedAgents = recentComms
      .filter(c => c.type === 'agent_activated')
      .map(c => c.agent);

    if (activatedAgents.length > 0) {
      const lastActive = activatedAgents[activatedAgents.length - 1];
      
      // Highlight the node
      const nodes = containerRef.current.querySelectorAll('.node');
      nodes.forEach(node => {
        const rect = node.querySelector('rect');
        if (rect) {
          const agentId = rect.getAttribute('id')?.split('-')[0];
          if (agentId === lastActive) {
            rect.setAttribute('fill', '#10b981');
            rect.setAttribute('stroke', '#059669');
            rect.setAttribute('stroke-width', '3');
          } else if (activatedAgents.includes(agentId || '')) {
            rect.setAttribute('fill', '#93c5fd');
          }
        }
      });
    }
  }, [communications]);

  if (error) {
    return (
      <div className="p-8 text-center">
        <div className="text-red-500 mb-2">Failed to render workflow graph</div>
        <div className="text-sm text-muted-foreground">{error}</div>
      </div>
    );
  }

  return (
    <div className="relative">
      <div
        ref={containerRef}
        className="mermaid-container overflow-auto p-4 bg-slate-50 dark:bg-slate-900 rounded-lg"
        style={{ minHeight: '400px' }}
      />
      
      {activeAgent && (
        <div className="absolute top-4 right-4 bg-white dark:bg-slate-800 p-3 rounded-lg shadow-lg border">
          <div className="text-sm font-medium">Selected Agent</div>
          <div className="text-lg font-bold text-primary">{activeAgent}</div>
        </div>
      )}

      {communications.length > 0 && (
        <div className="mt-2 flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span>Active</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-300" />
            <span>Executed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-gray-200" />
            <span>Pending</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkflowGraph;
