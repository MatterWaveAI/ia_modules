/**
 * Communication Log Component
 * 
 * Displays real-time agent communication logs with
 * filtering, search, and detailed event information
 */

import React, { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  MessageSquare, 
  Activity, 
  CheckCircle, 
  Clock, 
  Search,
  ChevronDown,
  ChevronRight
} from 'lucide-react';

interface Communication {
  timestamp: string;
  type: string;
  agent: string;
  data: any;
  duration?: number;
}

interface CommunicationLogProps {
  communications: Communication[];
  isLive?: boolean;
  detailed?: boolean;
}

const CommunicationLog: React.FC<CommunicationLogProps> = ({
  communications,
  isLive = false,
  detailed = false
}) => {
  const [filter, setFilter] = useState('');
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new communications arrive
  useEffect(() => {
    if (scrollRef.current && isLive) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [communications, isLive]);

  // Filter communications
  const filteredComms = communications.filter(comm => {
    if (!filter) return true;
    const searchStr = filter.toLowerCase();
    return (
      comm.agent.toLowerCase().includes(searchStr) ||
      comm.type.toLowerCase().includes(searchStr) ||
      JSON.stringify(comm.data).toLowerCase().includes(searchStr)
    );
  });

  // Toggle expanded state
  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedItems(newExpanded);
  };

  // Get icon for communication type
  const getIcon = (type: string) => {
    switch (type) {
      case 'agent_activated':
        return <Activity className="h-4 w-4 text-blue-500" />;
      case 'agent_completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'message':
        return <MessageSquare className="h-4 w-4 text-purple-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  // Get badge variant for type
  const getBadgeVariant = (type: string): "default" | "secondary" | "outline" => {
    switch (type) {
      case 'agent_activated':
        return 'default';
      case 'agent_completed':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  // Format timestamp
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      fractionalSecondDigits: 3
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Communication Log
            {isLive && (
              <Badge variant="destructive" className="ml-2">
                <Activity className="h-3 w-3 mr-1 animate-pulse" />
                LIVE
              </Badge>
            )}
          </CardTitle>
          <div className="text-sm text-muted-foreground">
            {filteredComms.length} {filteredComms.length === 1 ? 'event' : 'events'}
          </div>
        </div>
        
        {/* Search Filter */}
        <div className="relative mt-2">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Filter by agent, type, or content..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="pl-10"
          />
        </div>
      </CardHeader>
      
      <CardContent>
        <ScrollArea className="h-[500px]" ref={scrollRef}>
          <div className="space-y-2">
            {filteredComms.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {communications.length === 0 
                  ? 'No communications yet. Execute a workflow to see agent interactions.'
                  : 'No communications match your filter.'}
              </div>
            ) : (
              filteredComms.map((comm, index) => {
                const isExpanded = expandedItems.has(index);
                
                return (
                  <div
                    key={index}
                    className="border rounded-lg p-3 hover:bg-accent/50 transition-colors"
                  >
                    {/* Header */}
                    <div
                      className="flex items-center justify-between cursor-pointer"
                      onClick={() => toggleExpanded(index)}
                    >
                      <div className="flex items-center gap-3 flex-1">
                        {getIcon(comm.type)}
                        
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{comm.agent}</span>
                            <Badge variant={getBadgeVariant(comm.type)}>
                              {comm.type.replace('_', ' ')}
                            </Badge>
                          </div>
                          
                          <div className="text-sm text-muted-foreground mt-0.5">
                            {formatTime(comm.timestamp)}
                            {comm.duration && (
                              <span className="ml-2">
                                • Duration: {comm.duration.toFixed(2)}s
                              </span>
                            )}
                          </div>
                        </div>

                        {detailed && (
                          isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )
                        )}
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {(isExpanded || !detailed) && comm.data && (
                      <div className="mt-3 pl-7 space-y-2">
                        <div className="text-sm">
                          <div className="font-medium mb-1">Data:</div>
                          <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-40">
                            {JSON.stringify(comm.data, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default CommunicationLog;
