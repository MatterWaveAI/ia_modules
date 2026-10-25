"""
Agentic Design Pattern Steps for Pipelines

These demonstrate AI agent patterns as reusable pipeline steps.
Each pattern is a building block that can be composed into larger workflows.

Reusable Step subclasses:
1. ReflectionStep - Self-critique and iterative improvement
2. PlanningStep   - Multi-step goal decomposition
3. ToolUseStep    - Dynamic capability selection

Note: Agentic RAG and Metacognition patterns live in
`backend/services/pattern_service.py` as demo methods (agentic_rag_example,
metacognition_example) rather than reusable Step subclasses.
"""

from ia_modules.pipeline.core import Step
from ia_modules.utils.llm_adapters import SubprocessAgentAdapter
from typing import Dict, Any, List
import os


def _make_adapter() -> SubprocessAgentAdapter:
    """Create a SubprocessAgentAdapter with sensible defaults."""
    return SubprocessAgentAdapter(
        cwd=os.getcwd(),
        timeout_seconds=120.0,
    )


class ReflectionStep(Step):
    """
    Reflection Pattern: Self-critique and iterative improvement

    The agent generates output, critiques it against criteria, then refines.
    This is the core pattern behind models like Constitutional AI.

    Research: "Constitutional AI: Harmlessness from AI Feedback" (Anthropic, 2022)

    Example:
        step = ReflectionStep(
            name="improve_text",
            config={
                "initial_output": "This is my draft text.",
                "criteria": {
                    "clarity": "Text should be clear and concise",
                    "completeness": "All key points covered"
                },
                "max_iterations": 3
            }
        )
    """

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.adapter = _make_adapter()

    async def run(self, data: dict) -> dict:
        """Execute reflection pattern"""

        # Get parameters
        initial_output = data.get("initial_output") or self.config.get("initial_output")
        criteria = data.get("criteria") or self.config.get("criteria", {})
        max_iterations = data.get("max_iterations") or self.config.get("max_iterations", 3)

        if not initial_output:
            raise ValueError("initial_output is required for ReflectionStep")

        # Track iterations
        iterations = []
        current_output = initial_output

        for iteration in range(max_iterations):
            # Generate critique
            critique_prompt = self._build_critique_prompt(current_output, criteria)
            critique = await self.adapter.generate(prompt=critique_prompt)

            # Parse critique score
            score = self._parse_score(critique)

            # Track iteration
            iterations.append({
                "iteration": iteration + 1,
                "output": current_output,
                "critique": critique,
                "score": score
            })

            # Check if quality is acceptable
            if score >= 8.0:
                break

            # Generate improved version
            if iteration < max_iterations - 1:
                revision_prompt = self._build_revision_prompt(
                    current_output, critique, criteria
                )
                current_output = await self.adapter.generate(prompt=revision_prompt)

        return {
            "final_output": current_output,
            "final_score": score,
            "iterations": iterations,
            "total_iterations": len(iterations),
            "improved": score > self._parse_score(iterations[0]["critique"]) if iterations else False
        }

    def _build_critique_prompt(self, output: str, criteria: Dict[str, str]) -> str:
        """Build prompt for critique generation"""
        criteria_text = "\n".join([
            f"- {name}: {description}"
            for name, description in criteria.items()
        ])

        return f"""Critique the following output against these criteria:

{criteria_text}

Output to critique:
{output}

Provide:
1. Overall score (0-10)
2. Specific issues found
3. Suggestions for improvement

Format your response as:
Score: X/10
Issues: ...
Suggestions: ..."""

    def _build_revision_prompt(
        self,
        output: str,
        critique: str,
        criteria: Dict[str, str]
    ) -> str:
        """Build prompt for revision generation"""
        return f"""Revise the following output based on the critique:

Original output:
{output}

Critique:
{critique}

Please provide an improved version that addresses the issues raised."""

    def _parse_score(self, critique: str) -> float:
        """Parse score from critique text"""
        import re

        # Look for "Score: X/10" or "X/10" pattern
        match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*10', critique)
        if match:
            return float(match.group(1))

        # Look for standalone number at start of critique
        match = re.search(r'^(\d+(?:\.\d+)?)', critique.strip())
        if match:
            return float(match.group(1))

        return 5.0  # Default neutral score


class PlanningStep(Step):
    """
    Planning Pattern: Multi-step goal decomposition

    The agent breaks down complex goals into executable sub-tasks.
    This is foundational to frameworks like LangChain's ReAct and AutoGPT.

    Research: "Chain-of-Thought Prompting Elicits Reasoning" (Wei et al., 2022)

    Example:
        step = PlanningStep(
            name="plan_research",
            config={
                "goal": "Research renewable energy solutions",
                "constraints": ["Must complete in 2 hours", "Focus on solar"]
            }
        )
    """

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.adapter = _make_adapter()

    async def run(self, data: dict) -> dict:
        """Execute planning pattern"""

        # Get parameters
        goal = data.get("goal") or self.config.get("goal")
        constraints = data.get("constraints") or self.config.get("constraints", [])
        context = data.get("context") or self.config.get("context", {})

        if not goal:
            raise ValueError("goal is required for PlanningStep")

        # Generate plan
        planning_prompt = self._build_planning_prompt(goal, constraints, context)
        plan_text = await self.adapter.generate(prompt=planning_prompt)

        # Parse plan into steps
        steps = self._parse_steps(plan_text)

        # Validate plan (check if achievable)
        validation_prompt = self._build_validation_prompt(goal, steps, constraints)
        validation_text = await self.adapter.generate(prompt=validation_prompt)

        is_valid = "valid" in validation_text.lower()

        return {
            "goal": goal,
            "plan": steps,
            "plan_text": plan_text,
            "is_valid": is_valid,
            "validation_feedback": validation_text,
            "total_steps": len(steps),
            "estimated_time": self._estimate_time(steps)
        }

    def _build_planning_prompt(
        self,
        goal: str,
        constraints: List[str],
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for plan generation"""
        constraints_text = "\n".join([f"- {c}" for c in constraints]) if constraints else "None"
        context_text = "\n".join([f"- {k}: {v}" for k, v in context.items()]) if context else "None"

        return f"""Create a detailed step-by-step plan to achieve this goal:

Goal: {goal}

Constraints:
{constraints_text}

Available Context:
{context_text}

Provide a numbered list of concrete steps. For each step:
1. What action to take
2. Expected outcome
3. Dependencies (if any)

Format:
Step 1: [Action]
Expected: [Outcome]
Depends: [Dependencies]

Step 2: ..."""

    def _build_validation_prompt(
        self,
        goal: str,
        steps: List[Dict],
        constraints: List[str]
    ) -> str:
        """Build prompt for plan validation"""
        steps_text = "\n".join([
            f"Step {i+1}: {step['action']}"
            for i, step in enumerate(steps)
        ])

        return f"""Validate if this plan can achieve the goal:

Goal: {goal}

Plan:
{steps_text}

Constraints: {', '.join(constraints) if constraints else 'None'}

Is this plan valid and likely to succeed? Respond with:
- "VALID" if the plan is sound
- "INVALID" if there are critical flaws

Then explain your reasoning."""

    def _parse_steps(self, plan_text: str) -> List[Dict[str, Any]]:
        """Parse plan text into structured steps"""
        import re

        steps = []

        # Match patterns like "Step 1:", "1.", or numbered list
        step_pattern = r'(?:Step\s+)?(\d+)[:.)]\s*(.+?)(?=(?:Step\s+)?\d+[:.)]\s*|\Z)'
        matches = re.findall(step_pattern, plan_text, re.DOTALL | re.MULTILINE)

        for step_num, step_text in matches:
            # Extract action (first line)
            lines = [line.strip() for line in step_text.strip().split('\n') if line.strip()]
            action = lines[0] if lines else step_text.strip()

            # Look for "Expected:" and "Depends:" sections
            expected = ""
            depends = []

            for line in lines[1:]:
                if line.lower().startswith("expected:"):
                    expected = line.split(":", 1)[1].strip()
                elif line.lower().startswith("depends:"):
                    depends_text = line.split(":", 1)[1].strip()
                    depends = [d.strip() for d in depends_text.split(",")]

            steps.append({
                "step_number": int(step_num),
                "action": action,
                "expected_outcome": expected,
                "dependencies": depends
            })

        return steps

    def _estimate_time(self, steps: List[Dict]) -> str:
        """Estimate time required for plan"""
        # Simple heuristic: 15 min per step
        total_minutes = len(steps) * 15

        if total_minutes < 60:
            return f"{total_minutes} minutes"
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}h {minutes}m"


class ToolUseStep(Step):
    """
    Tool Use Pattern: Dynamic capability selection

    The agent decides which tools to use based on the task requirements.
    This is the pattern behind function calling in GPT-4 and Claude.

    Research: "Toolformer: Language Models Can Teach Themselves to Use Tools" (Meta, 2023)

    Example:
        step = ToolUseStep(
            name="solve_problem",
            config={
                "task": "Calculate compound interest for $1000 at 5% for 10 years",
                "available_tools": ["calculator", "search", "code_executor"]
            }
        )
    """

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.adapter = _make_adapter()

    async def run(self, data: dict) -> dict:
        """Execute tool use pattern"""

        task = data.get("task") or self.config.get("task")
        available_tools = data.get("available_tools") or self.config.get("available_tools", [])

        if not task:
            raise ValueError("task is required for ToolUseStep")

        # Tool selection
        tool_selection_prompt = self._build_tool_selection_prompt(task, available_tools)
        selection_text = await self.adapter.generate(prompt=tool_selection_prompt)

        selected_tools = self._parse_tool_selection(selection_text)

        # Simulate tool execution (in real implementation, would call actual tools)
        tool_results = []
        for tool_name in selected_tools:
            result = await self._execute_tool(tool_name, task)
            tool_results.append({
                "tool": tool_name,
                "result": result
            })

        # Synthesize final answer
        synthesis_prompt = self._build_synthesis_prompt(task, tool_results)
        final_answer = await self.adapter.generate(prompt=synthesis_prompt)

        return {
            "task": task,
            "selected_tools": selected_tools,
            "tool_results": tool_results,
            "final_answer": final_answer,
            "tools_used": len(selected_tools)
        }

    def _build_tool_selection_prompt(self, task: str, available_tools: List[str]) -> str:
        """Build prompt for tool selection"""
        tools_text = "\n".join([f"- {tool}" for tool in available_tools])

        return f"""You need to complete this task:
{task}

Available tools:
{tools_text}

Which tools would you use? List them in order of use.
Format: tool1, tool2, tool3"""

    def _parse_tool_selection(self, response: str) -> List[str]:
        """Parse selected tools from response"""
        # Extract comma-separated tool names
        tools = [t.strip() for t in response.split(",")]
        # Clean up (remove extra text)
        tools = [t.split()[0].lower() for t in tools if t.strip()]
        return tools

    async def _execute_tool(self, tool_name: str, task: str) -> str:
        """Execute tool (simulated)"""
        # In real implementation, this would call actual tool APIs
        if tool_name == "calculator":
            return "Calculation result: 1628.89"
        elif tool_name == "search":
            return "Search results: Compound interest formula is A = P(1 + r/n)^(nt)"
        elif tool_name == "code_executor":
            return "Executed: result = 1000 * (1 + 0.05)**10 = 1628.89"
        else:
            return f"Tool {tool_name} executed successfully"

    def _build_synthesis_prompt(self, task: str, tool_results: List[Dict]) -> str:
        """Build prompt for synthesizing final answer"""
        results_text = "\n".join([
            f"{r['tool']}: {r['result']}"
            for r in tool_results
        ])

        return f"""Based on these tool results, provide the final answer to the task:

Task: {task}

Tool Results:
{results_text}

Final Answer:"""


class WebScrapingStep(Step):
    """
    Web Scraping Step: Extract content from websites

    Uses the web scraper tool to collect content from specified URLs.
    Supports both single and batch scraping operations.

    Example:
        step = WebScrapingStep(
            name="scrape_websites",
            config={
                "urls": ["https://example.com", "https://example.org"],
                "extract_text": true,
                "include_metadata": true,
                "max_concurrent": 3
            }
        )
    """

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.scraper_tool = None
        self._init_scraper()

    def _init_scraper(self):
        """Initialize web scraper tool"""
        try:
            from ia_modules.tools.builtin_tools import create_web_scraper_batch_tool
            self.scraper_tool = create_web_scraper_batch_tool()
        except ImportError as e:
            self.logger.warning(f"Could not initialize web scraper: {e}")

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web scraping"""
        if not self.scraper_tool:
            return {
                "success": False,
                "error": "Web scraper tool not available",
                "scraped_content": []
            }

        urls = self.config.get("urls", [])
        if not urls:
            return {
                "success": False,
                "error": "No URLs specified",
                "scraped_content": []
            }

        try:
            # Execute batch scraping
            result = await self.scraper_tool.function(
                urls=urls,
                extract_text=self.config.get("extract_text", True),
                include_html=self.config.get("include_html", False),
                max_concurrent=self.config.get("max_concurrent", 3)
            )

            return {
                "success": True,
                "scraped_content": result["results"],
                "total_urls": result["total_urls"],
                "successful_scrapes": result["successful_scrapes"],
                "timestamp": result["timestamp"]
            }

        except Exception as e:
            self.logger.error(f"Web scraping failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "scraped_content": []
            }


class ContentAnalysisStep(Step):
    """
    Content Analysis Step: Analyze scraped web content

    Uses AI to analyze and summarize scraped content, extracting
    key insights and information.

    Example:
        step = ContentAnalysisStep(
            name="analyze_content",
            config={
                "analysis_type": "summarize_and_extract_key_points",
                "focus_areas": ["techniques", "challenges"],
                "max_tokens": 1000
            }
        )
    """

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.adapter = _make_adapter()

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute content analysis"""

        # Get scraped content from previous step
        scraped_data = context.get("scraped_content", [])
        if not scraped_data:
            return {
                "success": False,
                "error": "No scraped content available",
                "analysis": {}
            }

        analysis_type = self.config.get("analysis_type", "summarize")
        focus_areas = self.config.get("focus_areas", [])

        try:
            # Prepare content for analysis
            content_texts = []
            for item in scraped_data:
                if item.get("success", False):
                    title = item.get("title", "")
                    text = item.get("text_content", "")
                    if text:
                        content_texts.append(f"Title: {title}\nContent: {text[:2000]}...")  # Limit content length

            if not content_texts:
                return {
                    "success": False,
                    "error": "No successful content extractions",
                    "analysis": {}
                }

            combined_content = "\n\n".join(content_texts)

            # Build analysis prompt
            prompt = self._build_analysis_prompt(combined_content, analysis_type, focus_areas)

            # Get agent analysis
            result = await self.adapter.generate(prompt=prompt)

            return {
                "success": True,
                "analysis": {
                    "type": analysis_type,
                    "focus_areas": focus_areas,
                    "content_analyzed": len(content_texts),
                    "total_characters": sum(len(text) for text in content_texts),
                    "result": result,
                }
            }

        except Exception as e:
            self.logger.error(f"Content analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis": {}
            }

    def _build_analysis_prompt(self, content: str, analysis_type: str, focus_areas: List[str]) -> str:
        """Build analysis prompt based on type and focus areas"""
        focus_text = ""
        if focus_areas:
            focus_text = f"Focus on these areas: {', '.join(focus_areas)}."

        if analysis_type == "summarize_and_extract_key_points":
            return f"""Analyze the following web content and provide a comprehensive summary with key points extracted.

{focus_text}

Content to analyze:
{content}

Please provide:
1. Executive Summary (2-3 sentences)
2. Key Points by Category
3. Important Insights
4. Any Notable Patterns or Trends

Structure your response clearly with headers for each section."""

        elif analysis_type == "extract_technical_details":
            return f"""Extract technical details and specifications from the following web content.

{focus_text}

Content to analyze:
{content}

Please provide:
1. Technical Specifications
2. Implementation Details
3. Requirements or Prerequisites
4. Code Examples (if any)
5. API Information (if any)

Be specific and include relevant code snippets or technical details."""

        else:
            return f"""Analyze the following web content and provide insights.

{focus_text}

Content to analyze:
{content}

Provide a comprehensive analysis covering the main topics, key information, and any important details."""


class ReportGenerationStep(Step):
    """
    Report Generation Step: Create formatted reports from analysis

    Takes analysis results and generates well-formatted reports
    in various formats (markdown, text, etc.).

    Example:
        step = ReportGenerationStep(
            name="generate_report",
            config={
                "report_format": "markdown",
                "sections": ["summary", "findings", "recommendations"],
                "include_sources": true
            }
        )
    """

    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.adapter = _make_adapter()

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute report generation"""

        # Get analysis from previous step
        analysis = context.get("analysis", {})
        if not analysis:
            return {
                "success": False,
                "error": "No analysis data available",
                "report": ""
            }

        report_format = self.config.get("report_format", "markdown")
        sections = self.config.get("sections", ["summary", "findings"])
        include_sources = self.config.get("include_sources", False)

        # Get source information if requested
        sources = []
        if include_sources:
            scraped_content = context.get("scraped_content", [])
            sources = [
                {"title": item.get("title", ""), "url": item.get("url", "")}
                for item in scraped_content
                if item.get("success", False)
            ]

        try:
            # Build report generation prompt
            prompt = self._build_report_prompt(analysis, sections, sources, report_format)

            # Generate report
            report_content = await self.adapter.generate(prompt=prompt)

            return {
                "success": True,
                "report": report_content,
                "format": report_format,
                "sections": sections,
                "sources_included": include_sources,
            }

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "report": ""
            }

    def _build_report_prompt(self, analysis: Dict, sections: List[str], sources: List[Dict], format_type: str) -> str:
        """Build report generation prompt"""
        analysis_result = analysis.get("result", "")
        analysis_type = analysis.get("type", "")

        sources_text = ""
        if sources:
            sources_text = "\n\nSources:\n" + "\n".join([
                f"- {s['title']}: {s['url']}" for s in sources
            ])

        sections_text = ", ".join(sections)

        format_instructions = {
            "markdown": "Use Markdown formatting with headers, lists, and emphasis.",
            "text": "Use plain text with clear section headers and formatting.",
            "html": "Use HTML formatting with appropriate tags."
        }.get(format_type, "Use clear formatting with section headers.")

        return f"""Generate a comprehensive report based on the following analysis of web-scraped content.

Analysis Type: {analysis_type}
Analysis Results:
{analysis_result}

Required Sections: {sections_text}
Format: {format_type}
Formatting Instructions: {format_instructions}

{sources_text}

Please create a well-structured report that presents the information clearly and professionally. Ensure all sections are covered and the content flows logically."""
