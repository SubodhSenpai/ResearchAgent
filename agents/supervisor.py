from agents.base_agent import BaseAgent
from langchain_core.output_parsers import JsonOutputParser
import logging

logger = logging.getLogger(__name__)

SUPERVISOR_PROMPT = '''You are a research supervisor orchestrating a multi-agent research workflow.
Given a user query and the current state of research, your job is to:
1. Create a detailed research plan with specific sub-queries to investigate
2. Decompose the user's query into 3-5 focused sub-queries for thorough multi-angle search
3. Decide which agent should execute next based on current progress

You have access to these agents:
- **researcher**: Searches the web and knowledge base. Use when you need MORE data.
- **analyst**: Synthesizes raw search results into structured analysis. Use when you have enough data.
- **writer**: Composes the final polished answer. Use ONLY when analysis is complete and quality is adequate.

Output a JSON object with keys:
- plan: list of 3-6 research steps (strings) that outline your strategy
- sub_queries: list of 3-5 specific search queries to investigate different angles of the topic
- next_agent: one of ["researcher", "analyst", "writer"]
- reasoning: 1-2 sentences explaining your routing decision

ROUTING LOGIC (think step by step):
1. If NO search results exist → "researcher" (need to gather data)
2. If evidence_completeness < 70% or validator recommends "TARGETED_SEARCH" → "researcher" (fill identified gaps)
3. If search results exist BUT NO analysis → "analyst" (time to synthesize)
4. If analysis exists AND quality_score >= 0.75 → "writer" (ready to write)
5. If analysis exists AND contradictions identified → "researcher" (resolve conflicting evidence)
6. If iteration >= max_iterations → "writer" (force completion)

Output ONLY valid JSON, no other text.'''


class SupervisorAgent(BaseAgent):
    def __init__(self):
        super().__init__('Supervisor', SUPERVISOR_PROMPT)
        self.parser = JsonOutputParser()

    def run(self, state: dict) -> dict:
        iteration = state.get('iteration', 0)
        next_iter = iteration + 1

        has_analysis = bool(state.get('analysis'))
        has_search = bool(state.get('search_results'))
        quality_score = state.get('quality_score', 0.0)
        research_gaps = state.get('research_gaps', [])

        # Get memory context if available
        memory_context = ""
        try:
            from tools.memory_retrieval import MemoryRetrievalTool
            from auth.database import SessionLocal

            db = SessionLocal()
            user_id = state.get('user_id')
            if user_id:
                memory_tool = MemoryRetrievalTool(user_id, db)
                memory_context = memory_tool.get_supervisor_context(state.get('query', ''))
            db.close()
        except Exception as e:
            logger.debug(f"Could not retrieve memory context: {e}")

        # Format chat history if it exists
        chat_history = state.get('chat_history', [])
        chat_history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history]) if chat_history else "No previous history."

        # Use LLM for intelligent routing and planning
        session_id = state.get('session_id', 'unknown')
        self.trace(session_id, "input", {"query": state['query'], "iteration": next_iter})

        try:
            # ── Dynamic Prompting Safeguard ──────────────────────
            web_search_enabled = state.get('web_search_enabled', True)
            strict_guideline = ""
            if not web_search_enabled:
                strict_guideline = (
                    "\nSTRICT SAFEGUARD: Web search is DISABLED for this session. You MUST ONLY plan for and generate "
                    "sub-queries that focus on the user's local documents / knowledge base. Do NOT plan for any web-based "
                    "investigation.\n"
                )

            existing_knowledge = str(state.get('search_results', ''))[:2000]
            confidence_level = state.get('quality_score', 0)

            planner_template = """{strict_guideline}
            
            You are a Strategic Planner using Hierarchical Task Networks (HTN).
            
            GOAL: {query}
            EXISTING KNOWLEDGE: {knowledge}
            CONFIDENCE: {confidence}
            GAPS: {gaps}
            
            PLANNING RULES:
            1. Max depth: 2 levels (Objective -> Tactical Tasks).
            2. Stay within iteration limit: {next_iter}/5.
            
            Output a JSON object:
            - "strategic_objectives": ["obj1", "obj2"]
            - "tactical_tasks": ["task1", "task2"]
            - "next_agent": "researcher" | "analyst" | "writer"
            - "reasoning": "Strategy explanation"
            """
            planner_prompt = planner_template.format(
                strict_guideline=strict_guideline,
                query=state['query'],
                knowledge=existing_knowledge,
                confidence=confidence_level,
                gaps=state.get('evidence_gaps', []),
                next_iter=next_iter
            )
            self.trace(session_id, "prompt", {"content": planner_prompt})

            chain = self._build_chain(planner_prompt)
            result = chain.invoke({})
            
            import json, re
            match = re.search(r'\{.*\}', result.content, re.DOTALL)
            plan_data = json.loads(match.group()) if match else {}
            
            self.trace(session_id, "llm_response", {"raw": result.content, "parsed": plan_data})
            
            next_agent = plan_data.get('next_agent', 'researcher')
            objectives = plan_data.get('strategic_objectives', [])
            tasks = plan_data.get('tactical_tasks', [])
            plan = objectives + tasks
            sub_queries = plan_data.get('tactical_tasks', [])
            reasoning = plan_data.get('reasoning', '')
            
            # Validate next_agent
            if next_agent not in ('researcher', 'analyst', 'writer'):
                next_agent = 'researcher'

        except Exception as e:
            logger.warning(f"HTN Planning failed: {e}")
            self.trace(session_id, "error", {"detail": str(e)})
            # Fallback to deterministic routing
            next_agent, plan, sub_queries, reasoning = self._fallback_routing(
                state, has_search, has_analysis, quality_score, research_gaps
            )

        # Safety rails: enforce hard limits
        cap = state.get('max_iterations', 5)
        if next_iter >= cap:
            if next_agent == 'researcher':
                next_agent = 'analyst' if not has_analysis else 'writer'
            elif next_agent == 'analyst' and has_analysis:
                next_agent = 'writer'
            reasoning = f"Iteration limit ({cap}) reached — forcing {next_agent}"

        message = f'Supervisor (iteration {next_iter}/{cap}): routing to {next_agent} — {reasoning}'
        logger.info(message)
        self._log(f'Planning iteration {next_iter}: {state["query"][:60]}... -> {next_agent}')

        return {
            **state,
            'iteration': next_iter,
            'plan': plan if plan else state.get('plan', []),
            'sub_queries': sub_queries if sub_queries else state.get('sub_queries', []),
            '_next': next_agent,
            'messages': state['messages'] + [message],
        }

    def _fallback_routing(self, state, has_search, has_analysis, quality_score, research_gaps):
        """Deterministic fallback when LLM fails."""
        query = state['query']
        validator_rec = state.get('validator_recommendation', 'FINALIZE')

        if not has_search:
            return 'researcher', [f"Search for: {query}"], [query], 'No search results yet — gathering data'
        
        # Respect validator recommendation in fallback
        if validator_rec == 'TARGETED_SEARCH' and state.get('iteration', 0) < state.get('max_iterations', 5) - 1:
            return 'researcher', [], [], 'Validator recommends targeted search to fill gaps'

        if not has_analysis:
            return 'analyst', [], [], 'Have search results — synthesizing analysis'
        elif quality_score < 0.75 and research_gaps:
            return 'researcher', [], [], 'Quality below threshold with gaps — re-searching'
        else:
            return 'writer', [], [], 'Analysis complete — composing final answer'