import { useState, useEffect, useCallback, useRef } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Panel,
  getBezierPath,
  BaseEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { Plus, Save, Code, Eye, Columns, FileCode, Play } from 'lucide-react';
import StepNode from './StepNode';
import ParallelNode from './ParallelNode';
import DecisionNode from './DecisionNode';
import ModulePalette from './ModulePalette';
import StepCodeEditor from './StepCodeEditor';
import { formatEdge } from '../graph/utils/edgeFormatter';

// Custom edge that positions label near the source (20% along path)
function SourceLabelEdge({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, label, style, animated, markerEnd,
  data,
}) {
  const [edgePath] = getBezierPath({
    sourceX, sourceY, targetX, targetY,
    sourcePosition, targetPosition,
  });

  // Get point at ~20% along the bezier for label placement
  const t = 0.2;
  const labelX = (1 - t) * (1 - t) * (1 - t) * sourceX
    + 3 * (1 - t) * (1 - t) * t * ((sourceX + targetX) / 2)
    + 3 * (1 - t) * t * t * ((sourceX + targetX) / 2)
    + t * t * t * targetX;
  const labelY = (1 - t) * (1 - t) * (1 - t) * sourceY
    + 3 * (1 - t) * (1 - t) * t * sourceY
    + 3 * (1 - t) * t * t * targetY
    + t * t * t * targetY;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={style}
        markerEnd={markerEnd}
      />
      {label && (
        <foreignObject
          x={labelX - 4}
          y={labelY - 10}
          width={160}
          height={24}
          requiredExtensions="http://www.w3.org/1999/xhtml"
          className="overflow-visible pointer-events-none"
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: '#6b7280',
              background: 'rgba(249,250,251,0.92)',
              padding: '2px 6px',
              borderRadius: 4,
              whiteSpace: 'nowrap',
              width: 'fit-content',
            }}
          >
            {label}
          </div>
        </foreignObject>
      )}
    </>
  );
}

const nodeTypes = {
  step: StepNode,
  parallel: ParallelNode,
  decision: DecisionNode,
};

const edgeTypes = {
  sourceLabel: SourceLabelEdge,
};

// Run-button anchor geometry (decorative wire from Run button → first node).
// All coordinates are in container-relative pixel space.
const RUN_BUTTON_BOTTOM_Y = 52;   // just below the Run button panel
const ANCHOR_CX = 40;             // circle x, aligned with Run button center
const ANCHOR_CY = 76;             // circle y, sits below the button
const ANCHOR_R = 5;
const ANCHOR_LABEL_Y = ANCHOR_CY + 20;
// Fallback target if we can't yet project the real first node
const FALLBACK_TARGET_X = 260;
const FALLBACK_TARGET_Y = 200;

export default function VisualCanvas({ pipelineConfig, pipelineId, onConfigChange, onRun, isExecuting }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [showCodeEditor, setShowCodeEditor] = useState(false);
  const [selectedStepForCode, setSelectedStepForCode] = useState(null);
  const rfInstanceRef = useRef(null);
  const canvasRef = useRef(null);
  // One endpoint per pipeline parameter — each points to the matching input
  // port on whichever step reads {parameters.<name>}. Falls back to a single
  // endpoint aimed at the first node before layout resolves.
  const [anchorTargets, setAnchorTargets] = useState([
    { x: FALLBACK_TARGET_X, y: FALLBACK_TARGET_Y, name: '' },
  ]);

  // Initialize from pipeline config
  useEffect(() => {
    if (pipelineConfig) {
      const { nodes: initialNodes, edges: initialEdges } = convertConfigToGraph(pipelineConfig);
      setNodes(initialNodes);
      setEdges(initialEdges);
    }
  }, [pipelineConfig]);

  // Re-aim the decorative wires — one per pipeline parameter — at the matching
  // input port on the step that consumes {parameters.<name>}. Falls back to the
  // first node's left-middle when no parameter/port mapping can be resolved.
  const recomputeAnchorTarget = useCallback(() => {
    const rf = rfInstanceRef.current;
    const container = canvasRef.current;
    if (!onRun || !rf || !container || nodes.length === 0) return;

    const rect = container.getBoundingClientRect();

    // Map each declared parameter to (stepId, inputName) by scanning step inputs
    // for {parameters.<name>} source references. A parameter can feed multiple
    // steps, but we only draw from the anchor to the first hit per parameter
    // (so the "inputs" anchor shows one wire per parameter).
    const paramPattern = /^\{parameters\.([^}]+)\}$/;
    const params = Array.isArray(pipelineConfig?.parameters) ? pipelineConfig.parameters : [];
    const paramTargets = [];
    for (const p of params) {
      const paramName = p?.name;
      if (!paramName) continue;
      let hit = null;
      for (const step of pipelineConfig?.steps || []) {
        const inputs = Array.isArray(step.inputs) ? step.inputs : [];
        for (const inp of inputs) {
          const m = paramPattern.exec(inp?.source || '');
          if (m && m[1] === paramName) {
            hit = { stepId: step.id, inputName: inp.name };
            break;
          }
        }
        if (hit) break;
      }
      if (hit) paramTargets.push({ ...hit, paramName });
    }

    const projectNodePoint = (node) => {
      const flowX = node.position.x;
      const flowY = node.position.y + (node.height || 80) / 2;
      const screen = rf.flowToScreenPosition({ x: flowX, y: flowY });
      return { x: Math.round(screen.x - rect.left), y: Math.round(screen.y - rect.top) };
    };

    let next = [];
    if (paramTargets.length > 0) {
      for (const t of paramTargets) {
        // ReactFlow renders handles with data-nodeid and data-handleid attributes.
        const sel = `[data-nodeid="${t.stepId}"][data-handleid="in-${t.inputName}"]`;
        const handleEl = container.querySelector(sel);
        if (handleEl) {
          const h = handleEl.getBoundingClientRect();
          next.push({
            x: Math.round(h.left + h.width / 2 - rect.left),
            y: Math.round(h.top + h.height / 2 - rect.top),
            name: t.paramName,
          });
        }
      }
    }

    // Fallback: aim at the first node's left-middle if we couldn't resolve any ports
    if (next.length === 0) {
      const startId = pipelineConfig?.flow?.start_at || nodes[0]?.id;
      const firstNode = nodes.find((n) => n.id === startId) || nodes[0];
      if (!firstNode) return;
      const p = projectNodePoint(firstNode);
      next = [{ x: p.x, y: p.y, name: '' }];
    }

    // Bail out on same-value updates so pan/zoom idle frames don't re-render
    setAnchorTargets((prev) => {
      if (prev.length === next.length
          && prev.every((p, i) => p.x === next[i].x && p.y === next[i].y && p.name === next[i].name)) {
        return prev;
      }
      return next;
    });
  }, [nodes, pipelineConfig, onRun]);

  // Runs after layout settles and whenever nodes change.
  useEffect(() => {
    if (!onRun || nodes.length === 0) return;
    // fitView runs after our effect, so defer one frame
    const raf = requestAnimationFrame(recomputeAnchorTarget);
    return () => cancelAnimationFrame(raf);
  }, [recomputeAnchorTarget, nodes.length, onRun]);

  const onConnect = useCallback(
    (params) => {
      const newEdges = addEdge(
        {
          ...params,
          type: 'sourceLabel',
          animated: false,
          style: { stroke: '#3b82f6' },
        },
        edges
      );
      setEdges(newEdges);
      updatePipelineConfig(nodes, newEdges);
    },
    [edges, nodes]
  );

  const onNodeClick = useCallback((event, node) => {
    setSelectedNode(node);
    // Don't auto-open code editor on click, only when button is pressed
  }, []);

  const handleViewCode = useCallback((node) => {
    setSelectedStepForCode(node);
    setShowCodeEditor(true);
  }, []);

  const onNodesDelete = useCallback(
    (deleted) => {
      const remainingNodes = nodes.filter((n) => !deleted.find((d) => d.id === n.id));
      setNodes(remainingNodes);
      updatePipelineConfig(remainingNodes, edges);
    },
    [nodes, edges]
  );

  const onEdgesDelete = useCallback(
    (deleted) => {
      const remainingEdges = edges.filter((e) => !deleted.find((d) => d.id === e.id));
      setEdges(remainingEdges);
      updatePipelineConfig(nodes, remainingEdges);
    },
    [nodes, edges]
  );

  const addStepNode = useCallback(
    (stepType) => {
      const newNode = {
        id: `step-${Date.now()}`,
        type: 'step',
        position: {
          x: Math.random() * 400 + 100,
          y: Math.random() * 400 + 100,
        },
        data: {
          label: `New ${stepType}`,
          stepType: stepType,
          config: {},
        },
      };
      setNodes((nds) => [...nds, newNode]);
      updatePipelineConfig([...nodes, newNode], edges);
    },
    [nodes, edges]
  );

  const updateNodeData = useCallback(
    (nodeId, newData) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: { ...node.data, ...newData },
            };
          }
          return node;
        })
      );
      const updatedNodes = nodes.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, ...newData } } : node
      );
      updatePipelineConfig(updatedNodes, edges);
    },
    [nodes, edges]
  );

  const updatePipelineConfig = (currentNodes, currentEdges) => {
    const config = convertGraphToConfig(currentNodes, currentEdges, pipelineConfig);
    if (onConfigChange) {
      onConfigChange(config);
    }
  };

  return (
    <div className="h-full flex">
      {/* Module Palette */}
      <ModulePalette onAddStep={addStepNode} />

      {/* ReactFlow Canvas */}
      <div className="flex-1 relative" ref={canvasRef}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onNodesDelete={onNodesDelete}
          onEdgesDelete={onEdgesDelete}
          onInit={(instance) => { rfInstanceRef.current = instance; }}
          onMove={recomputeAnchorTarget}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultEdgeOptions={{
            type: 'sourceLabel',
            style: { strokeWidth: 1.5 },
          }}
          fitView
          attributionPosition="bottom-left"
        >
          <Background color="#e5e7eb" gap={16} />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              switch (node.type) {
                case 'step':
                  return '#3b82f6';
                case 'parallel':
                  return '#8b5cf6';
                case 'decision':
                  return '#f59e0b';
                default:
                  return '#6b7280';
              }
            }}
          />

          {/* Top Panel */}
          <Panel position="top-right">
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-lg p-2 flex gap-2">
              <button
                className="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center gap-2"
                onClick={() => updatePipelineConfig(nodes, edges)}
              >
                <Save className="w-4 h-4" />
                Save
              </button>
            </div>
          </Panel>

          {/* Run Panel (top-left) */}
          {onRun && (
            <Panel position="top-left">
              <div className="bg-white dark:bg-gray-900 rounded-lg shadow-lg p-2 flex gap-2">
                <button
                  className="px-3 py-2 text-sm bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  onClick={onRun}
                  disabled={isExecuting}
                >
                  <Play className="w-4 h-4" />
                  Run
                </button>
              </div>
            </Panel>
          )}
        </ReactFlow>

        {/* Decorative anchor + wire from Run button toward the first node's input side.
            The endpoint re-aims when nodes layout or the canvas pans/zooms. */}
        {onRun && (
          <svg
            className="absolute inset-0 pointer-events-none"
            width="100%"
            height="100%"
            style={{ overflow: 'visible' }}
          >
            <defs>
              <marker
                id="run-wire-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
              </marker>
            </defs>
            {/* Vertical connector from Run button down to the anchor circle */}
            <line
              x1={ANCHOR_CX}
              y1={RUN_BUTTON_BOTTOM_Y}
              x2={ANCHOR_CX}
              y2={ANCHOR_CY - ANCHOR_R}
              stroke="#10b981"
              strokeWidth="2"
            />
            {/* Anchor circle just below the Run button */}
            <circle
              cx={ANCHOR_CX}
              cy={ANCHOR_CY}
              r={ANCHOR_R}
              fill="#10b981"
              stroke="#ffffff"
              strokeWidth="2"
            />
            {/* "inputs" label under the circle */}
            <text
              x={ANCHOR_CX}
              y={ANCHOR_LABEL_Y}
              textAnchor="middle"
              fontSize="10"
              fontWeight="500"
              fill="#10b981"
            >
              inputs
            </text>
            {/* One curved dashed wire per pipeline parameter, each aimed at
                the input port that consumes {parameters.<name>}. */}
            {anchorTargets.map((t, i) => {
              const startX = ANCHOR_CX;
              const startY = ANCHOR_CY + ANCHOR_R;
              const endX = t.x;
              const endY = t.y;
              const midY = (startY + endY) / 2;
              const c1x = startX;
              const c1y = midY;
              const c2x = endX - 60;
              const c2y = endY;
              return (
                <path
                  key={`anchor-wire-${i}`}
                  d={`M ${startX} ${startY} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${endX} ${endY}`}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                  markerEnd="url(#run-wire-arrow)"
                />
              );
            })}
          </svg>
        )}
      </div>

      {/* Property Panel */}
      {selectedNode && (
        <PropertyPanel
          node={selectedNode}
          onUpdate={(data) => updateNodeData(selectedNode.id, data)}
          onClose={() => setSelectedNode(null)}
          onViewCode={() => handleViewCode(selectedNode)}
          pipelineId={pipelineId}
        />
      )}

      {/* Step Code Editor Sidebar */}
      {showCodeEditor && selectedStepForCode && pipelineId && (
        <div className="absolute top-0 right-0 w-1/2 h-full border-l dark:border-gray-700 bg-white dark:bg-gray-900 shadow-2xl z-50">
          <StepCodeEditor
            pipelineId={pipelineId}
            stepId={selectedStepForCode.id}
            onClose={() => {
              setShowCodeEditor(false);
              setSelectedStepForCode(null);
            }}
          />
        </div>
      )}
    </div>
  );
}

function PropertyPanel({ node, onUpdate, onClose, onViewCode, pipelineId }) {
  const [label, setLabel] = useState(node.data.label || '');
  const [config, setConfig] = useState(JSON.stringify(node.data.config || {}, null, 2));

  const handleSave = () => {
    try {
      const parsedConfig = JSON.parse(config);
      onUpdate({ label, config: parsedConfig });
    } catch (e) {
      alert('Invalid JSON configuration');
    }
  };

  return (
    <div className="w-80 bg-white dark:bg-gray-900 border-l dark:border-gray-700 shadow-lg p-4 overflow-y-auto">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Node Properties</h3>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
          ×
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
          <input
            type="text"
            value={node.data.stepType || node.type}
            disabled
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-400"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Configuration</label>
          <textarea
            value={config}
            onChange={(e) => setConfig(e.target.value)}
            rows={10}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono text-xs focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="space-y-2">
          <button
            onClick={handleSave}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Apply Changes
          </button>

          {/* View Code button - only show for step nodes and if pipeline has ID */}
          {node.type === 'step' && pipelineId && onViewCode && (
            <button
              onClick={onViewCode}
              className="w-full px-4 py-2 border border-blue-600 dark:border-blue-500 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-950/30 flex items-center justify-center gap-2"
            >
              <FileCode className="w-4 h-4" />
              View Step Code
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Convert pipeline config to ReactFlow graph
function convertConfigToGraph(config) {
  const nodes = [];
  const edges = [];

  if (!config.steps || config.steps.length === 0) {
    return { nodes, edges };
  }

  // Build adjacency lists for graph traversal
  const outgoing = {}; // from_step -> [to_steps]
  const incoming = {}; // to_step -> [from_steps]

  config.steps.forEach(step => {
    outgoing[step.id] = [];
    incoming[step.id] = [];
  });

  // Convert flow paths to edges and build adjacency lists
  // Support both 'from_step'/'to_step' (pipeline JSON) and 'from'/'to' (legacy) formats
  // First pass: build adjacency lists
  const normalizedPaths = [];
  if (config.flow?.paths) {
    config.flow.paths.forEach((path) => {
      const fromStep = path.from_step || path.from;
      const toStep = path.to_step || path.to;
      normalizedPaths.push({ from_step: fromStep, to_step: toStep, condition: path.condition });

      if (outgoing[fromStep]) {
        outgoing[fromStep].push(toStep);
      }
      if (incoming[toStep]) {
        incoming[toStep].push(fromStep);
      }
    });
  }

  // BFS to assign levels (needed for back-edge detection)
  const levels = {};
  const visited = new Set();
  const startStep = config.flow?.start_at || config.steps[0].id;
  const queue = [[startStep, 0]];
  visited.add(startStep);
  levels[startStep] = 0;
  let maxLevel = 0;

  while (queue.length > 0) {
    const [currentId, level] = queue.shift();
    maxLevel = Math.max(maxLevel, level);
    (outgoing[currentId] || []).forEach(childId => {
      if (!visited.has(childId)) {
        visited.add(childId);
        levels[childId] = level + 1;
        queue.push([childId, level + 1]);
      }
    });
  }
  config.steps.forEach(step => {
    if (levels[step.id] === undefined) levels[step.id] = maxLevel + 1;
  });

  // Build step lookups needed for edge generation and port inference
  const stepsById = {};
  const stepNameMap = {};
  config.steps.forEach(step => {
    stepsById[step.id] = step;
    stepNameMap[step.id] = step.name;
  });

  // Build a lookup: for each step, index its inputs by source step ID
  // This lets us find which specific ports an edge should connect to
  const stepInputsBySource = {}; // targetStepId -> { sourceStepId -> [{ inputName, outputField }] }
  // Track which input/output names are actually wired via {steps.X.output.Y} references,
  // so we can hide orphan ports that nothing reads from / writes to.
  const wiredInputs = {};  // targetStepId -> Set of input names
  const wiredOutputs = {}; // sourceStepId -> Set of output field names

  const sourcePattern = /^\{steps\.([^.]+)\.output\.([^}]+)\}$/;
  config.steps.forEach(step => {
    const inputs = step.inputs || [];
    const inputList = Array.isArray(inputs)
      ? inputs.filter(i => typeof i === 'object' && i.name)
      : Object.entries(inputs).map(([k, v]) => ({ name: k, source: v }));

    inputList.forEach(inp => {
      const match = sourcePattern.exec(inp.source || '');
      if (match) {
        const [, srcStepId, outputField] = match;
        if (!stepInputsBySource[step.id]) stepInputsBySource[step.id] = {};
        if (!stepInputsBySource[step.id][srcStepId]) stepInputsBySource[step.id][srcStepId] = [];
        stepInputsBySource[step.id][srcStepId].push({ inputName: inp.name, outputField });
        if (!wiredInputs[step.id]) wiredInputs[step.id] = new Set();
        wiredInputs[step.id].add(inp.name);
        if (!wiredOutputs[srcStepId]) wiredOutputs[srcStepId] = new Set();
        wiredOutputs[srcStepId].add(outputField);
      }
    });
  });

  // Second pass: generate edges with human-readable labels and back-edge detection
  normalizedPaths.forEach((path, index) => {
    const sourceLevel = levels[path.from_step] ?? 0;
    const targetLevel = levels[path.to_step] ?? 0;
    const isBackEdge = targetLevel <= sourceLevel && path.from_step !== path.to_step;

    const { label, style } = formatEdge(path, isBackEdge);

    // Determine port handles for this edge
    const fromStep = stepsById[path.from_step];
    const toStep = stepsById[path.to_step];
    const fromHasExplicitOutputs = fromStep && normalizePortNames(fromStep.outputs).length > 0;
    const toHasExplicitInputs = toStep && normalizePortNames(toStep.inputs).length > 0;

    // Check if there are explicit source references linking specific ports
    const portLinks = stepInputsBySource[path.to_step]?.[path.from_step];
    const edgeLabel = label || (path.condition?.type === 'always' ? undefined : path.condition?.type);

    if (portLinks && portLinks.length > 0) {
      // Emit one edge per port link so every data dependency is visible
      portLinks.forEach((link, linkIdx) => {
        edges.push({
          id: `edge-${index}-${linkIdx}`,
          source: path.from_step,
          target: path.to_step,
          sourceHandle: `out-${link.outputField}`,
          targetHandle: `in-${link.inputName}`,
          type: 'sourceLabel',
          animated: !isBackEdge,
          // Only label the first edge in a bundle to avoid overlapping labels
          label: linkIdx === 0 ? edgeLabel : undefined,
          style,
        });
      });
      return;
    }

    let sourceHandle;
    let targetHandle;
    if (!fromHasExplicitOutputs && !toHasExplicitInputs) {
      // Inferred ports: handle IDs are based on connected step names
      const fromName = stepNameMap[path.from_step] || path.from_step;
      const toName = stepNameMap[path.to_step] || path.to_step;
      sourceHandle = `out-${toName}`;
      targetHandle = `in-${fromName}`;
    } else {
      // Mixed: one side has explicit ports, other doesn't — pick first available
      if (fromHasExplicitOutputs) {
        const firstOutput = normalizePortNames(fromStep.outputs)[0];
        if (firstOutput) sourceHandle = `out-${firstOutput}`;
      } else {
        const toName = stepNameMap[path.to_step] || path.to_step;
        sourceHandle = `out-${toName}`;
      }
      if (toHasExplicitInputs) {
        const firstInput = normalizePortNames(toStep.inputs)[0];
        if (firstInput) targetHandle = `in-${firstInput}`;
      } else {
        const fromName = stepNameMap[path.from_step] || path.from_step;
        targetHandle = `in-${fromName}`;
      }
    }

    edges.push({
      id: `edge-${index}`,
      source: path.from_step,
      target: path.to_step,
      sourceHandle,
      targetHandle,
      type: 'sourceLabel',
      animated: !isBackEdge,
      label: edgeLabel,
      style,
    });
  });

  // Third pass: emit data edges for {steps.X.output.Y} references whose
  // (source, target) pair isn't already covered by a flow path. This surfaces
  // data dependencies that skip over the flow (e.g. last step reading from first).
  const flowPairs = new Set(
    normalizedPaths.map(p => `${p.from_step}->${p.to_step}`)
  );
  let dataEdgeCounter = 0;
  Object.entries(stepInputsBySource).forEach(([targetId, sourcesMap]) => {
    Object.entries(sourcesMap).forEach(([sourceId, links]) => {
      if (flowPairs.has(`${sourceId}->${targetId}`)) return;
      const sourceLevel = levels[sourceId] ?? 0;
      const targetLevel = levels[targetId] ?? 0;
      const isBackEdge = targetLevel <= sourceLevel && sourceId !== targetId;
      links.forEach((link) => {
        edges.push({
          id: `data-edge-${dataEdgeCounter++}`,
          source: sourceId,
          target: targetId,
          sourceHandle: `out-${link.outputField}`,
          targetHandle: `in-${link.inputName}`,
          type: 'sourceLabel',
          animated: !isBackEdge,
          style: { stroke: '#94a3b8', strokeDasharray: '4 4', strokeWidth: 1.5 },
        });
      });
    });
  });

  // Build inferred ports from flow connections for steps that lack explicit inputs/outputs
  const inferredInputs = {};  // stepId -> Set of source step names
  const inferredOutputs = {}; // stepId -> Set of target step names

  normalizedPaths.forEach(path => {
    const fromId = path.from_step;
    const toId = path.to_step;
    if (!inferredOutputs[fromId]) inferredOutputs[fromId] = new Set();
    if (!inferredInputs[toId]) inferredInputs[toId] = new Set();
    inferredOutputs[fromId].add(stepNameMap[toId] || toId);
    inferredInputs[toId].add(stepNameMap[fromId] || fromId);
  });

  // Resolve final port lists per step (needed for accurate node sizing).
  // Explicit ports are filtered down to only the ones actually wired via
  // {steps.X.output.Y} references — but only when at least one is wired.
  // If none of a step's declared ports are wired (e.g. first step reads
  // from {parameters.*}, or last step's outputs have no downstream consumer),
  // keep all declared ports so boundary nodes don't render as empty.
  const resolvedPorts = {};
  config.steps.forEach(step => {
    const explicitInputs = normalizePortNames(step.inputs);
    const explicitOutputs = normalizePortNames(step.outputs);
    const inputsWired = wiredInputs[step.id];
    const outputsWired = wiredOutputs[step.id];

    let inputs;
    if (explicitInputs.length > 0) {
      const filtered = inputsWired
        ? explicitInputs.filter(name => inputsWired.has(name))
        : [];
      inputs = filtered.length > 0 ? filtered : explicitInputs;
    } else {
      inputs = [...(inferredInputs[step.id] || [])];
    }

    let outputs;
    if (explicitOutputs.length > 0) {
      const filtered = outputsWired
        ? explicitOutputs.filter(name => outputsWired.has(name))
        : [];
      outputs = filtered.length > 0 ? filtered : explicitOutputs;
    } else {
      outputs = [...(inferredOutputs[step.id] || [])];
    }

    resolvedPorts[step.id] = { inputs, outputs };
  });

  // Dagre layout — hierarchical with edge-crossing minimization
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: 'LR',       // left-to-right flow
    nodesep: 60,          // vertical gap between nodes in same rank
    ranksep: 200,         // horizontal gap between ranks
    edgesep: 30,          // gap between edges
    marginx: 40,
    marginy: 40,
    ranker: 'network-simplex', // best crossing minimization
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Add nodes to dagre with estimated sizes based on actual port count
  const NODE_BASE_WIDTH = 200;
  const NODE_BASE_HEIGHT = 70;
  const PORT_ROW_HEIGHT = 22;

  config.steps.forEach(step => {
    const { inputs: ins, outputs: outs } = resolvedPorts[step.id];
    const portRows = Math.max(ins.length, outs.length, 0);
    const height = NODE_BASE_HEIGHT + portRows * PORT_ROW_HEIGHT;
    g.setNode(step.id, { width: NODE_BASE_WIDTH, height });
  });

  // Add forward edges to dagre (skip back-edges to avoid layout cycles)
  const dagreForwardTargets = new Set(); // nodes that have at least one forward incoming edge
  normalizedPaths.forEach(path => {
    const sourceLevel = levels[path.from_step] ?? 0;
    const targetLevel = levels[path.to_step] ?? 0;
    const isBackEdge = targetLevel <= sourceLevel && path.from_step !== path.to_step;
    if (!isBackEdge) {
      g.setEdge(path.from_step, path.to_step);
      dagreForwardTargets.add(path.to_step);
    }
  });

  // For nodes that lost all incoming edges (only reached via back-edges),
  // add a phantom edge from any node at the previous BFS level so dagre
  // places them at the correct rank instead of rank 0.
  const nodesByLevel = {};
  config.steps.forEach(step => {
    const lvl = levels[step.id] ?? 0;
    if (!nodesByLevel[lvl]) nodesByLevel[lvl] = [];
    nodesByLevel[lvl].push(step.id);
  });

  config.steps.forEach(step => {
    const lvl = levels[step.id] ?? 0;
    if (lvl > 0 && !dagreForwardTargets.has(step.id)) {
      // This node has no forward incoming edges — anchor it to correct rank
      const prevLevelNodes = nodesByLevel[lvl - 1];
      if (prevLevelNodes && prevLevelNodes.length > 0) {
        g.setEdge(prevLevelNodes[0], step.id, { weight: 0, minlen: 1 });
      }
    }
  });

  dagre.layout(g);

  // Extract positions from dagre (center coords → top-left for ReactFlow)
  const positions = {};
  config.steps.forEach(step => {
    const node = g.node(step.id);
    if (node) {
      positions[step.id] = {
        x: node.x - node.width / 2,
        y: node.y - node.height / 2,
      };
    }
  });

  // Convert steps to nodes with calculated positions
  config.steps.forEach(step => {
    const { inputs, outputs } = resolvedPorts[step.id];
    nodes.push({
      id: step.id,
      type: 'step',
      position: positions[step.id] || { x: 100, y: 100 },
      data: {
        label: step.name,
        stepType: step.type,
        config: step.config,
        inputs,
        outputs,
      },
    });
  });

  return { nodes, edges };
}

// Convert ReactFlow graph to pipeline config
function convertGraphToConfig(nodes, edges, existingConfig) {
  const steps = nodes.map((node) => ({
    id: node.id,
    name: node.data.label,
    type: node.data.stepType || 'task',
    config: node.data.config || {},
  }));

  const paths = edges.map((edge) => ({
    from_step: edge.source,
    to_step: edge.target,
    condition: edge.label ? { description: edge.label } : { type: 'always' },
  }));

  return {
    ...existingConfig,
    steps,
    flow: {
      start_at: steps[0]?.id || '',
      paths,
    },
  };
}

/**
 * Normalize various input/output formats into a simple array of port name strings.
 * Handles: array of objects [{name: "x"}], object {x: "..."}, array of strings ["x"], or undefined.
 */
function normalizePortNames(ports) {
  if (!ports) return [];
  if (Array.isArray(ports)) {
    return ports.map(p => (typeof p === 'string' ? p : p.name)).filter(Boolean);
  }
  if (typeof ports === 'object') {
    return Object.keys(ports);
  }
  return [];
}
