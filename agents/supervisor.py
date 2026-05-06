from agents.base_agent import BaseAgent
from langchain_core.output_parsers import JsonOutputParser
import logging

logger = logging.getLogger(__name__)

SUPERVISOR_PROMPT = '''You are a research supervisor orchestrating a multi-agent research workflow.
Given a user query and current research state, create a step-by-step research plan and decide the next agent to execute.

Output a JSON object with keys:
- plan: list of research steps (strings) - refined based on what's been done so far
- next_agent: one of [researcher, analyst, writer, end]
- reasoning: brief explanation of why you chose this next step

CRITICAL ROUTING RULES (apply in order):
1. If NO search results exist yet → route to "researcher" (must gather data first)
2. If search results exist BUT NO analysis yet → route to "analyst" (synthesize findings into analysis)
3. If analysis exists AND quality_score >= 0.75 → route to "writer" (quality is good, finalize answer)
4. If analysis exists AND quality_score < 0.75 → route to "writer" anyway (accept current quality, finalize)
5. When done with analysis → always route to "writer" for final composition

DECISION TABLE:
- No search results? → researcher
- Have search results, no analysis? → analyst
- Have analysis? → writer
- Unsure? → Default to analyst

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

        # DETERMINISTIC ROUTING: Don't ask LLM, use explicit logic
        if not has_search:
            next_agent = 'researcher'
            reasoning = 'No search results yet - gathering information'
        elif not has_analysis:
            next_agent = 'analyst'
            reasoning = 'Have search results - synthesizing analysis'
        else:
            next_agent = 'writer'
            reasoning = 'Have analysis - composing final answer'

        message = f'Supervisor (iteration {next_iter}): routing to {next_agent} - {reasoning}'
        logger.info(message)
        self._log(f'Planning iteration {next_iter}: {state["query"][:60]}... -> {next_agent}')

        return {
            **state,
            'iteration': next_iter,
            'plan': state.get('plan', []),
            '_next': next_agent,
            'messages': state['messages'] + [message],
        }