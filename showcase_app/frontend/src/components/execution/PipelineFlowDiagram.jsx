import React from 'react'
import FlowNode from './FlowNode'
import FlowConnector from './FlowConnector'

export default function PipelineFlowDiagram({ steps }) {
  return (
    <div className="flex flex-col items-center space-y-4 max-w-3xl mx-auto">
      {steps.map((step, index) => (
        <React.Fragment key={index}>
          <FlowNode step={step} index={index} />
          {index < steps.length - 1 && <FlowConnector />}
        </React.Fragment>
      ))}
    </div>
  )
}
