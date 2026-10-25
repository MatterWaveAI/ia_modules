import React from 'react'
import { ArrowDown } from 'lucide-react'

export default function FlowConnector() {
  return (
    <div className="flex flex-col items-center py-2">
      <ArrowDown className="text-gray-400" size={32} strokeWidth={2} />
    </div>
  )
}
