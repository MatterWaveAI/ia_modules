"""
Advanced Tools API endpoints.

This module provides REST API endpoints for demonstrating advanced tool capabilities,
including tool execution, tool chaining, dynamic tool creation, and tool registry management.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models

class ToolType(str, Enum):
    """Types of tools."""
    FUNCTION = "function"  # Python function
    API = "api"  # API endpoint
    COMMAND = "command"  # System command
    CUSTOM = "custom"  # Custom implementation


class ParameterType(str, Enum):
    """Parameter types for tools."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolParameter(BaseModel):
    """Parameter definition for a tool."""
    name: str = Field(..., description="Parameter name")
    type: ParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(True, description="Whether parameter is required")
    default: Optional[Any] = Field(None, description="Default value")
    enum: Optional[List[Any]] = Field(None, description="Allowed values (if enumerated)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "query",
                "type": "string",
                "description": "Search query",
                "required": True
            }
        }


class ToolDefinition(BaseModel):
    """Definition of a tool."""
    id: str = Field(..., description="Unique tool ID")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="What the tool does")
    type: ToolType = Field(..., description="Tool type")
    parameters: List[ToolParameter] = Field(..., description="Tool parameters")
    returns: str = Field(..., description="Description of return value")
    version: str = Field("1.0.0", description="Tool version")
    tags: List[str] = Field(default_factory=list, description="Tool tags")
    capabilities: List[str] = Field(default_factory=list, description="Tool capabilities")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web for information",
                "type": "api",
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "Search query",
                        "required": True
                    }
                ],
                "returns": "Search results as JSON",
                "version": "1.0.0",
                "tags": ["search", "web"],
                "capabilities": ["web_search"]
            }
        }


class ExecuteToolRequest(BaseModel):
    """Request to execute a tool."""
    tool_id: str = Field(..., description="ID of tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters")
    context: Dict[str, Any] = Field(default_factory=dict, description="Execution context")
    timeout_seconds: float = Field(30, gt=0, description="Execution timeout")

    class Config:
        json_schema_extra = {
            "example": {
                "tool_id": "web_search",
                "parameters": {"query": "latest AI news"},
                "timeout_seconds": 30
            }
        }


class ToolExecutionResult(BaseModel):
    """Result from tool execution."""
    success: bool = Field(..., description="Whether execution succeeded")
    tool_id: str = Field(..., description="ID of executed tool")
    result: Any = Field(..., description="Execution result")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ToolChainStep(BaseModel):
    """A step in a tool chain."""
    tool_id: str = Field(..., description="Tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters")
    map_output: Optional[Dict[str, str]] = Field(None, description="Map output to next step's input")
    condition: Optional[str] = Field(None, description="Condition for executing this step")

    class Config:
        json_schema_extra = {
            "example": {
                "tool_id": "web_search",
                "parameters": {"query": "{user_query}"},
                "map_output": {"results": "search_results"}
            }
        }


class CreateChainRequest(BaseModel):
    """Request to create a tool chain."""
    name: str = Field(..., description="Chain name")
    description: str = Field(..., description="What the chain does")
    steps: List[ToolChainStep] = Field(..., description="Chain steps in order")
    parallel_execution: bool = Field(False, description="Execute steps in parallel when possible")
    error_handling: str = Field("stop", description="Error handling: 'stop', 'skip', or 'continue'")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Research Chain",
                "description": "Search, analyze, and summarize information",
                "steps": [
                    {
                        "tool_id": "web_search",
                        "parameters": {"query": "{topic}"},
                        "map_output": {"results": "search_results"}
                    },
                    {
                        "tool_id": "summarize",
                        "parameters": {"text": "{search_results}"},
                        "map_output": {"summary": "final_output"}
                    }
                ],
                "error_handling": "stop"
            }
        }


class CreateChainResponse(BaseModel):
    """Response from creating a tool chain."""
    success: bool = Field(..., description="Whether chain was created")
    chain_id: str = Field(..., description="Unique chain ID")
    name: str = Field(..., description="Chain name")
    steps_count: int = Field(..., description="Number of steps in chain")
    message: str = Field(..., description="Success message")


class ExecuteChainRequest(BaseModel):
    """Request to execute a tool chain."""
    input_data: Dict[str, Any] = Field(..., description="Input data for chain")
    context: Dict[str, Any] = Field(default_factory=dict, description="Execution context")
    timeout_seconds: float = Field(300, gt=0, description="Total timeout for chain")

    class Config:
        json_schema_extra = {
            "example": {
                "input_data": {"topic": "quantum computing"},
                "timeout_seconds": 120
            }
        }


class ChainStepResult(BaseModel):
    """Result from a chain step."""
    step_number: int = Field(..., description="Step number")
    tool_id: str = Field(..., description="Tool executed")
    success: bool = Field(..., description="Whether step succeeded")
    result: Any = Field(None, description="Step result")
    execution_time_ms: float = Field(..., description="Step execution time")
    error: Optional[str] = Field(None, description="Error if failed")


class ExecuteChainResponse(BaseModel):
    """Response from executing a tool chain."""
    success: bool = Field(..., description="Whether chain execution succeeded")
    chain_id: str = Field(..., description="Chain ID")
    final_output: Any = Field(..., description="Final chain output")
    step_results: List[ChainStepResult] = Field(..., description="Results from each step")
    total_execution_time_ms: float = Field(..., description="Total execution time")
    steps_executed: int = Field(..., description="Number of steps executed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ToolRegistryEntry(BaseModel):
    """Entry in the tool registry."""
    tool: ToolDefinition = Field(..., description="Tool definition")
    registered_at: float = Field(..., description="Registration timestamp")
    usage_count: int = Field(0, description="Number of times used")
    last_used: Optional[float] = Field(None, description="Last usage timestamp")
    enabled: bool = Field(True, description="Whether tool is enabled")


class GetRegistryResponse(BaseModel):
    """Response with tool registry."""
    tools: List[ToolRegistryEntry] = Field(..., description="Registered tools")
    total: int = Field(..., description="Total number of tools")
    by_type: Dict[str, int] = Field(..., description="Count by tool type")
    by_capability: Dict[str, int] = Field(..., description="Count by capability")


# In-memory storage
tool_registry: Dict[str, ToolRegistryEntry] = {}
tool_chains: Dict[str, Dict[str, Any]] = {}
chain_counter = 0


# Built-in tools
BUILTIN_TOOLS = {
    "calculator": ToolDefinition(
        id="calculator",
        name="Calculator",
        description="Perform mathematical calculations",
        type=ToolType.FUNCTION,
        parameters=[
            ToolParameter(
                name="expression",
                type=ParameterType.STRING,
                description="Mathematical expression to evaluate",
                required=True
            )
        ],
        returns="Calculation result as number",
        version="1.0.0",
        tags=["math", "calculation"],
        capabilities=["arithmetic"]
    ),
    "web_search": ToolDefinition(
        id="web_search",
        name="Web Search",
        description="Search the web for information",
        type=ToolType.API,
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="Search query",
                required=True
            ),
            ToolParameter(
                name="max_results",
                type=ParameterType.INTEGER,
                description="Maximum results to return",
                required=False,
                default=10
            )
        ],
        returns="Search results as list of dictionaries",
        version="1.0.0",
        tags=["search", "web", "information"],
        capabilities=["web_search", "information_retrieval"]
    ),
    "summarize": ToolDefinition(
        id="summarize",
        name="Text Summarizer",
        description="Summarize long text into concise summary",
        type=ToolType.FUNCTION,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="Text to summarize",
                required=True
            ),
            ToolParameter(
                name="max_length",
                type=ParameterType.INTEGER,
                description="Maximum summary length in words",
                required=False,
                default=100
            )
        ],
        returns="Summarized text",
        version="1.0.0",
        tags=["nlp", "summarization"],
        capabilities=["text_processing", "summarization"]
    ),
    "data_analysis": ToolDefinition(
        id="data_analysis",
        name="Data Analyzer",
        description="Analyze data and generate insights",
        type=ToolType.FUNCTION,
        parameters=[
            ToolParameter(
                name="data",
                type=ParameterType.ARRAY,
                description="Data to analyze",
                required=True
            ),
            ToolParameter(
                name="analysis_type",
                type=ParameterType.STRING,
                description="Type of analysis",
                required=False,
                default="descriptive",
                enum=["descriptive", "statistical", "trends"]
            )
        ],
        returns="Analysis results as dictionary",
        version="1.0.0",
        tags=["data", "analysis"],
        capabilities=["data_analysis", "statistics"]
    ),
    "code_executor": ToolDefinition(
        id="code_executor",
        name="Code Executor",
        description="Execute code in sandboxed environment",
        type=ToolType.COMMAND,
        parameters=[
            ToolParameter(
                name="code",
                type=ParameterType.STRING,
                description="Code to execute",
                required=True
            ),
            ToolParameter(
                name="language",
                type=ParameterType.STRING,
                description="Programming language",
                required=True,
                enum=["python", "javascript", "bash"]
            )
        ],
        returns="Execution output",
        version="1.0.0",
        tags=["code", "execution"],
        capabilities=["code_execution"]
    )
}


# Initialize registry with built-in tools
import time  # noqa: E402
for tool_id, tool_def in BUILTIN_TOOLS.items():
    tool_registry[tool_id] = ToolRegistryEntry(
        tool=tool_def,
        registered_at=time.time(),
        usage_count=0,
        last_used=None,
        enabled=True
    )


# Dependency injection
def get_tools_service(request: Request):
    """Get tools service from app state."""
    # For now, return None. In production, return request.app.state.services.tools_service
    return None


# Mock tool execution functions
def execute_calculator(expression: str) -> float:
    """Execute calculator tool."""
    try:
        # Safe evaluation (in production, use safer method)
        return eval(expression, {"__builtins__": {}}, {})
    except Exception as e:
        raise ValueError(f"Invalid expression: {e}")


def execute_web_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Execute web search tool."""
    return [
        {
            "title": f"Result {i+1} for: {query}",
            "url": f"https://example.com/result{i+1}",
            "snippet": f"This is a mock search result snippet for {query}"
        }
        for i in range(min(max_results, 5))
    ]


def execute_summarize(text: str, max_length: int = 100) -> str:
    """Execute summarize tool."""
    words = text.split()
    if len(words) <= max_length:
        return text
    return " ".join(words[:max_length]) + "..."


# API Endpoints

@router.post("/execute", response_model=ToolExecutionResult)
async def execute_tool(
    request: ExecuteToolRequest,
    service=Depends(get_tools_service)
) -> ToolExecutionResult:
    """
    Execute a tool with given parameters.

    This endpoint executes a registered tool and returns the result.
    Supports various tool types including functions, APIs, and commands.

    Example:
        ```python
        response = await client.post("/api/tools/execute", json={
            "tool_id": "calculator",
            "parameters": {"expression": "2 + 2"},
            "timeout_seconds": 30
        })
        print(f"Result: {response.result}")
        ```
    """
    import time

    try:
        start_time = time.time()

        # Check if tool exists
        if request.tool_id not in tool_registry:
            raise HTTPException(
                status_code=404,
                detail=f"Tool '{request.tool_id}' not found in registry"
            )

        tool_entry = tool_registry[request.tool_id]

        if not tool_entry.enabled:
            raise HTTPException(
                status_code=400,
                detail=f"Tool '{request.tool_id}' is disabled"
            )

        # Execute tool (mock implementation)
        result = None
        if request.tool_id == "calculator":
            result = execute_calculator(request.parameters.get("expression", "0"))
        elif request.tool_id == "web_search":
            result = execute_web_search(
                request.parameters.get("query", ""),
                request.parameters.get("max_results", 10)
            )
        elif request.tool_id == "summarize":
            result = execute_summarize(
                request.parameters.get("text", ""),
                request.parameters.get("max_length", 100)
            )
        else:
            result = f"Mock result from {request.tool_id}"

        # Update usage stats
        tool_entry.usage_count += 1
        tool_entry.last_used = time.time()

        execution_time_ms = (time.time() - start_time) * 1000

        logger.info(f"Executed tool {request.tool_id} in {execution_time_ms:.2f}ms")

        return ToolExecutionResult(
            success=True,
            tool_id=request.tool_id,
            result=result,
            execution_time_ms=execution_time_ms,
            error=None,
            metadata={
                "tool_type": tool_entry.tool.type.value,
                "parameters": request.parameters
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing tool: {e}", exc_info=True)
        execution_time_ms = (time.time() - start_time) * 1000
        return ToolExecutionResult(
            success=False,
            tool_id=request.tool_id,
            result=None,
            execution_time_ms=execution_time_ms,
            error=str(e),
            metadata={}
        )


@router.post("/chain/create", response_model=CreateChainResponse)
async def create_tool_chain(
    request: CreateChainRequest,
    service=Depends(get_tools_service)
) -> CreateChainResponse:
    """
    Create a tool chain.

    A tool chain is a sequence of tool executions where the output of one
    tool can be mapped to the input of the next tool. Chains enable complex
    workflows by composing multiple tools.

    Features:
    - Sequential or parallel execution
    - Output mapping between steps
    - Conditional execution
    - Error handling strategies

    Example:
        ```python
        response = await client.post("/api/tools/chain/create", json={
            "name": "Research Pipeline",
            "description": "Search and summarize",
            "steps": [
                {
                    "tool_id": "web_search",
                    "parameters": {"query": "{topic}"},
                    "map_output": {"results": "search_data"}
                },
                {
                    "tool_id": "summarize",
                    "parameters": {"text": "{search_data}"}
                }
            ]
        })
        chain_id = response.chain_id
        ```
    """
    global chain_counter

    try:
        # Validate all tools exist
        for step in request.steps:
            if step.tool_id not in tool_registry:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tool '{step.tool_id}' not found in registry"
                )

        # Generate chain ID
        chain_counter += 1
        chain_id = f"chain_{chain_counter}"

        # Create chain
        tool_chains[chain_id] = {
            "chain_id": chain_id,
            "name": request.name,
            "description": request.description,
            "steps": [step.model_dump() for step in request.steps],
            "parallel_execution": request.parallel_execution,
            "error_handling": request.error_handling,
            "created_at": time.time(),
            "usage_count": 0
        }

        logger.info(f"Created tool chain {chain_id} with {len(request.steps)} steps")

        return CreateChainResponse(
            success=True,
            chain_id=chain_id,
            name=request.name,
            steps_count=len(request.steps),
            message=f"Tool chain '{request.name}' created successfully with ID {chain_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tool chain: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create tool chain: {str(e)}"
        )


@router.post("/chain/execute/{chain_id}", response_model=ExecuteChainResponse)
async def execute_tool_chain(
    chain_id: str,
    request: ExecuteChainRequest,
    service=Depends(get_tools_service)
) -> ExecuteChainResponse:
    """
    Execute a tool chain.

    Executes all steps in a chain sequentially or in parallel (based on chain config),
    passing data between steps according to the output mapping.

    Example:
        ```python
        response = await client.post(f"/api/tools/chain/execute/{chain_id}", json={
            "input_data": {"topic": "artificial intelligence"},
            "timeout_seconds": 120
        })
        print(f"Final output: {response.final_output}")
        ```
    """
    import time

    try:
        start_time = time.time()

        # Check if chain exists
        if chain_id not in tool_chains:
            raise HTTPException(
                status_code=404,
                detail=f"Tool chain '{chain_id}' not found"
            )

        chain = tool_chains[chain_id]
        steps = chain["steps"]
        step_results = []
        context = request.input_data.copy()

        # Execute steps
        for i, step in enumerate(steps):
            step_start = time.time()

            try:
                # Replace placeholders in parameters
                params = {}
                for key, value in step["parameters"].items():
                    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                        context_key = value[1:-1]
                        params[key] = context.get(context_key, value)
                    else:
                        params[key] = value

                # Execute tool
                tool_result = await execute_tool(
                    ExecuteToolRequest(
                        tool_id=step["tool_id"],
                        parameters=params,
                        context=request.context
                    ),
                    service
                )

                step_time_ms = (time.time() - step_start) * 1000

                # Map output to context
                if step.get("map_output") and tool_result.success:
                    for output_key, context_key in step["map_output"].items():
                        if output_key == "results" or output_key == "result":
                            context[context_key] = tool_result.result
                        else:
                            context[context_key] = tool_result.result

                step_results.append(ChainStepResult(
                    step_number=i + 1,
                    tool_id=step["tool_id"],
                    success=tool_result.success,
                    result=tool_result.result,
                    execution_time_ms=step_time_ms,
                    error=tool_result.error
                ))

                # Handle errors
                if not tool_result.success:
                    if chain["error_handling"] == "stop":
                        break
                    elif chain["error_handling"] == "skip":
                        continue

            except Exception as e:
                step_time_ms = (time.time() - step_start) * 1000
                step_results.append(ChainStepResult(
                    step_number=i + 1,
                    tool_id=step["tool_id"],
                    success=False,
                    result=None,
                    execution_time_ms=step_time_ms,
                    error=str(e)
                ))

                if chain["error_handling"] == "stop":
                    break

        # Determine final output
        final_output = context
        if step_results and step_results[-1].success:
            final_output = step_results[-1].result

        total_time_ms = (time.time() - start_time) * 1000

        # Update usage
        chain["usage_count"] += 1

        logger.info(
            f"Executed chain {chain_id}: {len(step_results)}/{len(steps)} steps "
            f"in {total_time_ms:.2f}ms"
        )

        return ExecuteChainResponse(
            success=all(r.success for r in step_results),
            chain_id=chain_id,
            final_output=final_output,
            step_results=step_results,
            total_execution_time_ms=total_time_ms,
            steps_executed=len(step_results),
            metadata={
                "chain_name": chain["name"],
                "error_handling": chain["error_handling"]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing tool chain: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute tool chain: {str(e)}"
        )


@router.get("/registry", response_model=GetRegistryResponse)
async def get_tool_registry(
    tool_type: Optional[ToolType] = None,
    capability: Optional[str] = None,
    service=Depends(get_tools_service)
) -> GetRegistryResponse:
    """
    Get the tool registry.

    Returns all registered tools with their metadata, usage statistics,
    and capabilities. Can be filtered by tool type or capability.

    Example:
        ```python
        registry = await client.get("/api/tools/registry")
        for entry in registry.tools:
            print(f"{entry.tool.name}: {entry.tool.description}")
        ```
    """
    try:
        # Filter tools
        filtered_tools = []
        for entry in tool_registry.values():
            if tool_type and entry.tool.type != tool_type:
                continue
            if capability and capability not in entry.tool.capabilities:
                continue
            filtered_tools.append(entry)

        # Count by type
        by_type = {}
        for entry in filtered_tools:
            type_str = entry.tool.type.value
            by_type[type_str] = by_type.get(type_str, 0) + 1

        # Count by capability
        by_capability = {}
        for entry in filtered_tools:
            for cap in entry.tool.capabilities:
                by_capability[cap] = by_capability.get(cap, 0) + 1

        return GetRegistryResponse(
            tools=filtered_tools,
            total=len(filtered_tools),
            by_type=by_type,
            by_capability=by_capability
        )

    except Exception as e:
        logger.error(f"Error getting tool registry: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tool registry: {str(e)}"
        )


@router.get("/chains")
async def list_tool_chains(
    service=Depends(get_tools_service)
):
    """
    List all tool chains.

    Returns all created tool chains with their configurations.

    Example:
        ```python
        chains = await client.get("/api/tools/chains")
        for chain in chains["chains"]:
            print(f"{chain['name']}: {len(chain['steps'])} steps")
        ```
    """
    try:
        chains = list(tool_chains.values())

        return {
            "chains": chains,
            "total": len(chains)
        }

    except Exception as e:
        logger.error(f"Error listing tool chains: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tool chains: {str(e)}"
        )


@router.post("/register", response_model=ToolRegistryEntry)
async def register_tool(
    tool: ToolDefinition,
    service=Depends(get_tools_service)
) -> ToolRegistryEntry:
    """
    Register a new tool in the registry.

    Allows dynamic registration of custom tools at runtime.

    Example:
        ```python
        tool = {
            "id": "my_custom_tool",
            "name": "Custom Tool",
            "description": "Does something custom",
            "type": "function",
            "parameters": [...],
            "returns": "Custom result"
        }
        entry = await client.post("/api/tools/register", json=tool)
        ```
    """
    try:
        if tool.id in tool_registry:
            raise HTTPException(
                status_code=400,
                detail=f"Tool '{tool.id}' already registered"
            )

        import time
        entry = ToolRegistryEntry(
            tool=tool,
            registered_at=time.time(),
            usage_count=0,
            last_used=None,
            enabled=True
        )

        tool_registry[tool.id] = entry

        logger.info(f"Registered new tool: {tool.id}")

        return entry

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering tool: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register tool: {str(e)}"
        )


# Web Scraping Models

class ScrapedContent(BaseModel):
    """Scraped content from a web page."""
    url: str = Field(..., description="Source URL")
    title: str = Field("", description="Page title")
    text_content: str = Field("", description="Extracted text content")
    html_content: Optional[str] = Field(None, description="Raw HTML content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    success: bool = Field(True, description="Whether scraping was successful")
    error_message: str = Field("", description="Error message if scraping failed")


class WebScrapingRequest(BaseModel):
    """Request model for web scraping."""
    url: str = Field(..., description="URL to scrape")
    extract_text: bool = Field(True, description="Whether to extract clean text content")
    include_html: bool = Field(False, description="Whether to include raw HTML in result")
    follow_redirects: bool = Field(True, description="Whether to follow HTTP redirects")


class BatchWebScrapingRequest(BaseModel):
    """Request model for batch web scraping."""
    urls: List[str] = Field(..., description="List of URLs to scrape")
    extract_text: bool = Field(True, description="Whether to extract clean text content")
    include_html: bool = Field(False, description="Whether to include raw HTML in result")
    max_concurrent: int = Field(3, description="Maximum concurrent requests", ge=1, le=10)


class WebScrapingResponse(BaseModel):
    """Response model for web scraping."""
    success: bool = Field(..., description="Whether the operation was successful")
    data: ScrapedContent = Field(..., description="Scraped content data")
    timestamp: str = Field(..., description="Timestamp of the operation")
    execution_time: float = Field(..., description="Execution time in seconds")


class BatchWebScrapingResponse(BaseModel):
    """Response model for batch web scraping."""
    success: bool = Field(..., description="Whether the operation was successful")
    data: List[ScrapedContent] = Field(..., description="List of scraped content")
    total_urls: int = Field(..., description="Total number of URLs processed")
    successful_scrapes: int = Field(..., description="Number of successful scrapes")
    timestamp: str = Field(..., description="Timestamp of the operation")
    execution_time: float = Field(..., description="Execution time in seconds")


# Web Scraping Endpoints

@router.post(
    "/web-scraper/scrape",
    response_model=WebScrapingResponse,
    summary="Scrape content from a single URL",
    description="Extract content from a web page including text, metadata, and optionally HTML.",
    tags=["web-scraping"]
)
async def scrape_url(request: WebScrapingRequest) -> WebScrapingResponse:
    """
    Scrape content from a single URL.

    This endpoint uses the web scraper tool to extract content from websites,
    with options for text extraction, HTML inclusion, and redirect following.
    """
    import time
    from ia_modules.tools.builtin_tools import create_web_scraper_tool

    start_time = time.time()

    try:
        # Get the web scraper tool
        scraper_tool = create_web_scraper_tool()

        # Execute scraping
        result = await scraper_tool.function(
            url=request.url,
            extract_text=request.extract_text,
            include_html=request.include_html,
            follow_redirects=request.follow_redirects
        )

        execution_time = time.time() - start_time

        # Convert result to response format
        scraped_content = ScrapedContent(
            url=result.get("url", request.url),
            title=result.get("title", ""),
            text_content=result.get("text_content", ""),
            html_content=result.get("html_content"),
            metadata=result.get("metadata", {}),
            success=result.get("success", False),
            error_message=result.get("error_message", "")
        )

        return WebScrapingResponse(
            success=result.get("success", False),
            data=scraped_content,
            timestamp=result.get("timestamp", datetime.now().isoformat()),
            execution_time=execution_time
        )

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Web scraping failed: {e}", exc_info=True)

        return WebScrapingResponse(
            success=False,
            data=ScrapedContent(
                url=request.url,
                success=False,
                error_message=str(e)
            ),
            timestamp=datetime.now().isoformat(),
            execution_time=execution_time
        )


@router.post(
    "/web-scraper/scrape-batch",
    response_model=BatchWebScrapingResponse,
    summary="Scrape content from multiple URLs",
    description="Extract content from multiple web pages concurrently with rate limiting.",
    tags=["web-scraping"]
)
async def scrape_urls_batch(request: BatchWebScrapingRequest) -> BatchWebScrapingResponse:
    """
    Scrape content from multiple URLs concurrently.

    This endpoint uses the batch web scraper tool to extract content from multiple websites
    simultaneously, with configurable concurrency limits and rate limiting.
    """
    import time
    from ia_modules.tools.builtin_tools import create_web_scraper_batch_tool

    start_time = time.time()

    try:
        # Get the batch web scraper tool
        scraper_tool = create_web_scraper_batch_tool()

        # Execute batch scraping
        result = await scraper_tool.function(
            urls=request.urls,
            extract_text=request.extract_text,
            include_html=request.include_html,
            max_concurrent=request.max_concurrent
        )

        execution_time = time.time() - start_time

        # Convert results to response format
        scraped_contents = []
        for item in result.get("results", []):
            scraped_content = ScrapedContent(
                url=item.get("url", ""),
                title=item.get("title", ""),
                text_content=item.get("text_content", ""),
                html_content=item.get("html_content"),
                metadata=item.get("metadata", {}),
                success=item.get("success", False),
                error_message=item.get("error_message", "")
            )
            scraped_contents.append(scraped_content)

        return BatchWebScrapingResponse(
            success=True,
            data=scraped_contents,
            total_urls=result.get("total_urls", len(request.urls)),
            successful_scrapes=result.get("successful_scrapes", 0),
            timestamp=result.get("timestamp", datetime.now().isoformat()),
            execution_time=execution_time
        )

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Batch web scraping failed: {e}", exc_info=True)

        # Return error response with empty results
        return BatchWebScrapingResponse(
            success=False,
            data=[],
            total_urls=len(request.urls),
            successful_scrapes=0,
            timestamp=datetime.now().isoformat(),
            execution_time=execution_time
        )


@router.get(
    "/web-scraper/info",
    summary="Get web scraper information",
    description="Get information about available web scraping capabilities and configuration.",
    tags=["web-scraping"]
)
async def get_scraper_info() -> Dict[str, Any]:
    """
    Get information about web scraping capabilities.

    Returns details about supported features, rate limits, and configuration.
    """
    return {
        "capabilities": {
            "single_url_scraping": True,
            "batch_scraping": True,
            "text_extraction": True,
            "html_preservation": True,
            "metadata_extraction": True,
            "robots_txt_compliance": True,
            "rate_limiting": True,
            "redirect_following": True
        },
        "limits": {
            "max_concurrent_requests": 10,
            "default_delay_between_requests": 1.0,
            "max_content_length": "10MB",
            "timeout": "30s"
        },
        "supported_content_types": [
            "text/html",
            "application/xhtml+xml"
        ],
        "safety_features": [
            "robots.txt checking",
            "rate limiting",
            "content size limits",
            "timeout protection"
        ]
    }
