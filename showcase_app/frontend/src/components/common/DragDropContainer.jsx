import React, { useState } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { ComponentRenderer } from './ComponentRenderer'
import DraggableItem from './DraggableItem'
import ComponentToolbar from './ComponentToolbar'
import { pipelinesAPI } from '../../services/api'

// Main drag and drop container
export default function DragDropContainer({
  children,
  onLayoutChange,
  layoutKey = 'execution-detail-layout',
  onTemplateImport,
  execution,
  pipeline,
  jobId,
  telemetryData
}) {
  const [items, setItems] = useState(() => {
    // Try to load saved layout from localStorage
    const savedLayout = localStorage.getItem(layoutKey)
    if (savedLayout) {
      try {
        return JSON.parse(savedLayout)
      } catch (error) {
        console.warn('Failed to parse saved layout:', error)
      }
    }

    // Initialize with default layout if no children provided or no saved layout
    if (!children || children.length === 0) {
      return [
        { id: 'execution-header', component: 'ExecutionHeader', visible: true, props: { onBack: () => {} } },
        { id: 'execution-status', component: 'ExecutionStatusCard', visible: true, props: {} },
        { id: 'execution-error', component: 'ExecutionError', visible: true, props: {} },
        { id: 'execution-timeline', component: 'ExecutionTimeline', visible: true, props: {} },
        { id: 'pipeline-graph', component: 'PipelineGraphSection', visible: true, props: {} },
        { id: 'span-timeline', component: 'SpanTimeline', visible: true, props: {} },
        { id: 'checkpoints', component: 'CheckpointList', visible: true, props: {} },
        { id: 'conversation-history', component: 'ConversationHistory', visible: true, props: {} },
        { id: 'replay-comparison', component: 'ReplayComparison', visible: true, props: {} },
        { id: 'decision-timeline', component: 'DecisionTimeline', visible: true, props: {} },
        { id: 'step-details', component: 'StepDetailsList', visible: true, props: {} },
        { id: 'data-viewer', component: 'DataViewer', visible: true, props: {} },
      ]
    }

    // Convert children to items array
    return React.Children.map(children, (child, index) => {
      if (!child) return null;
      const componentType = child.props?.children || child.props?.['data-component'] || 'UnknownComponent'
      return {
        id: child.props?.id || `item-${index}`,
        component: componentType,
        visible: true,
        props: child.props?.['data-props'] || {},
      }
    }).filter(Boolean)
  })

  // Save layout to localStorage whenever it changes
  React.useEffect(() => {
    localStorage.setItem(layoutKey, JSON.stringify(items))
  }, [items, layoutKey])

  // Handle template import
  const handleTemplateImport = (templateItems, templateName) => {
    // Replace current items with template items
    setItems(templateItems)

    // Notify parent of template import
    if (onTemplateImport) {
      onTemplateImport(templateItems, templateName)
    }

    // Also notify of layout change
    if (onLayoutChange) {
      onLayoutChange(templateItems)
    }
  }

  const handleCreateFromTemplate = (template) => {
    // For now, just import the template - could be extended to create new pipeline
    handleTemplateImport(convertPipelineToItems(template), template.name)
  }

  const convertPipelineToItems = (pipeline) => {
    const config = pipeline.config || {}
    const steps = config.steps || []

    // Convert steps to draggable items
    const stepItems = steps.map((step, index) => ({
      id: step.id || `step-${index}`,
      component: getComponentTypeFromStep(step),
      visible: true,
      props: {
        step: {
          name: step.name,
          config: step.config || {}
        }
      }
    }))

    // Add default UI components
    const defaultItems = [
      { id: 'execution-header', component: 'ExecutionHeader', visible: true, props: { onBack: () => {} } },
      { id: 'execution-status', component: 'ExecutionStatusCard', visible: true, props: {} },
      { id: 'execution-timeline', component: 'ExecutionTimeline', visible: true, props: {} },
      { id: 'pipeline-graph', component: 'PipelineGraphSection', visible: true, props: {} },
      { id: 'step-details', component: 'StepDetailsList', visible: true, props: {} },
    ]

    return [...defaultItems, ...stepItems]
  }

  const getComponentTypeFromStep = (step) => {
    const stepClass = step.step_class || ''
    const name = step.name || ''

    // Map step classes to component types
    const classMapping = {
      'WebScrapingStep': 'WebScrapingStep',
      'ContentAnalysisStep': 'ContentAnalysisStep',
      'ReportGenerationStep': 'ReportGenerationStep',
      'PlanningStep': 'PlanningStep',
      'ToolUseStep': 'ToolUseStep',
      'ReflectionStep': 'ReflectionStep',
    }

    // Also check by name patterns
    const nameMapping = {
      'agent': 'AgentStep',
      'llm': 'LLMCallStep',
      'guardrail': 'GuardrailsStep',
      'tool': 'ToolUseStep',
    }

    return classMapping[stepClass] ||
           Object.entries(nameMapping).find(([key, value]) =>
             name.toLowerCase().includes(key)
           )?.[1] ||
           'AgentStep' // Default fallback
  }

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  function handleDragEnd(event) {
    const { active, over } = event

    if (active.id !== over.id) {
      setItems((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id)
        const newIndex = items.findIndex((item) => item.id === over.id)

        const newItems = arrayMove(items, oldIndex, newIndex)

        // Notify parent of layout change
        if (onLayoutChange) {
          onLayoutChange(newItems)
        }

        return newItems
      })
    }
  }

  function handleRemoveItem(itemId) {
    setItems((items) => {
      const newItems = items.map(item =>
        item.id === itemId ? { ...item, visible: false } : item
      )

      if (onLayoutChange) {
        onLayoutChange(newItems)
      }

      return newItems
    })
  }

  const handleSaveAsPipeline = async () => {
    const pipelineName = prompt('Enter pipeline name:')
    if (!pipelineName) return

    // Convert current layout to pipeline configuration
    const pipelineConfig = convertItemsToPipeline(items, pipelineName)

    try {
      await pipelinesAPI.create(pipelineConfig)
      alert(`Pipeline "${pipelineName}" saved successfully!`)
    } catch (error) {
      console.error('Failed to save pipeline:', error)
      alert('Failed to save pipeline. Check console for details.')
    }
  }

  const handleResetLayout = () => {
    // Reset to default layout
    const defaultItems = [
      { id: 'execution-header', component: 'ExecutionHeader', visible: true, props: { onBack: () => {} } },
      { id: 'execution-status', component: 'ExecutionStatusCard', visible: true, props: {} },
      { id: 'execution-error', component: 'ExecutionError', visible: true, props: {} },
      { id: 'execution-timeline', component: 'ExecutionTimeline', visible: true, props: {} },
      { id: 'pipeline-graph', component: 'PipelineGraphSection', visible: true, props: {} },
      { id: 'span-timeline', component: 'SpanTimeline', visible: true, props: {} },
      { id: 'checkpoints', component: 'CheckpointList', visible: true, props: {} },
      { id: 'conversation-history', component: 'ConversationHistory', visible: true, props: {} },
      { id: 'replay-comparison', component: 'ReplayComparison', visible: true, props: {} },
      { id: 'decision-timeline', component: 'DecisionTimeline', visible: true, props: {} },
      { id: 'step-details', component: 'StepDetailsList', visible: true, props: {} },
      { id: 'data-viewer', component: 'DataViewer', visible: true, props: {} },
    ]
    setItems(defaultItems)
    if (onLayoutChange) {
      onLayoutChange(defaultItems)
    }
  }

  const handleAddItem = (componentType) => {
    const newItem = {
      id: `${componentType.toLowerCase()}-${Date.now()}`,
      component: componentType,
      visible: true,
      props: {}
    }
    setItems(prevItems => [...prevItems, newItem])
    if (onLayoutChange) {
      onLayoutChange([...items, newItem])
    }
  }

  const convertItemsToPipeline = (layoutItems, name) => {
    // Extract step components from layout
    const steps = layoutItems
      .filter(item => isStepComponent(item.component))
      .map((item, index) => ({
        id: item.id,
        name: item.props?.step?.name || `${item.component} ${index + 1}`,
        step_class: getStepClassFromComponent(item.component),
        module: "showcase_app.backend.pipelines.pattern_steps",
        config: item.props?.step?.config || {}
      }))

    // Create basic flow (sequential for now)
    const flow = {
      start_at: steps[0]?.id || "start",
      paths: steps.slice(0, -1).map((step, index) => ({
        from: step.id,
        to: steps[index + 1].id,
        condition: { type: "always" }
      }))
    }

    return {
      name,
      description: `Custom pipeline created from drag-drop layout`,
      version: "1.0.0",
      config: {
        steps,
        flow
      },
      metadata: {
        author: "drag-drop-editor",
        tags: ["custom", "drag-drop"],
        category: "user-created"
      }
    }
  }

  const isStepComponent = (componentType) => {
    const stepComponents = [
      'AgentStep', 'LLMCallStep', 'GuardrailsStep', 'ToolUseStep',
      'WebScrapingStep', 'ContentAnalysisStep', 'ReportGenerationStep',
      'PlanningStep', 'ReflectionStep'
    ]
    return stepComponents.includes(componentType)
  }

  const getStepClassFromComponent = (componentType) => {
    const mapping = {
      'AgentStep': 'AgentStep',
      'LLMCallStep': 'LLMCallStep',
      'GuardrailsStep': 'GuardrailsStep',
      'ToolUseStep': 'ToolUseStep',
      'WebScrapingStep': 'WebScrapingStep',
      'ContentAnalysisStep': 'ContentAnalysisStep',
      'ReportGenerationStep': 'ReportGenerationStep',
      'PlanningStep': 'PlanningStep',
      'ReflectionStep': 'ReflectionStep',
    }
    return mapping[componentType] || componentType
  }

  const visibleItems = items.filter(item => item.visible)

  return (
    <div className="space-y-4">
      {/* Toolbar for adding new components */}
      <ComponentToolbar
        availableComponents={[
          'ExecutionHeader',
          'ExecutionStatusCard',
          'ExecutionError',
          'ExecutionTimeline',
          'PipelineGraphSection',
          'SpanTimeline',
          'CheckpointList',
          'ConversationHistory',
          'ReplayComparison',
          'DecisionTimeline',
          'StepDetailsList',
          'DataViewer',
          'AgentStep',
          'LLMCallStep',
          'GuardrailsStep',
          'ToolUseStep',
        ]}
        onAddComponent={handleAddItem}
        onSavePipeline={handleSaveAsPipeline}
        onResetLayout={handleResetLayout}
      />

      {/* Drag and drop area */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={visibleItems.map(item => item.id)}
          strategy={verticalListSortingStrategy}
        >
          {visibleItems.map((item) => (
            <DraggableItem
              key={item.id}
              id={item.id}
              onRemove={handleRemoveItem}
            >
              {/* Render the actual component based on type */}
              <ComponentRenderer
                componentType={item.component}
                itemId={item.id}
                {...item.props}
                // Pass execution context to all components
                execution={execution}
                pipeline={pipeline}
                jobId={jobId}
                telemetryData={telemetryData}
              />
            </DraggableItem>
          ))}
        </SortableContext>
      </DndContext>
    </div>
  )
}