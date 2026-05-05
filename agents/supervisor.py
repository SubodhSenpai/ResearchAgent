from agents.base_agent import BaseAgent
from langchain_core.output_parsers import JsonOutputParser

SUPERVISOR_PROMPT = ''' You are a research supervisor. Given a user query, create a step-by-step research plan.
Output a JSON object with keys:
- plan: list of research steps (strings)
- next_agent: one of [researcher, analyst, critic, writer, end]
- reasoning: why you chose this next step
Output ONLY valid JSON, no other text.'''

class SupervisorAgent(BaseAgent):
    def __init__(self):
        super().__init__('supervisor', SUPERVISOR_PROMPT)
        self.parser = JsonOutputParser()

    def run(self, state: dict) -> dict:
        self._log(f'Planning for: {state["query"]}')
        chain = self._build_chain(
            f'Query: {query}\n Current state: {current_state}'
        ) | self.parser

        result = chain.invoke({
            'query': state['query'],
            'current_state': f'iteration={state["iteration"]},'
            f'has_analysis = {bool(state.get("analysis"))},'
            f'quality_score = {state.get("quality_score", 0)}'
        })

        return{
            **state,
            'plan': result.get('plan', []),
            '_next': result.get('next_aget', 'researcher'),
            'messages': state['messages'] + [
                f'Supervisor: routing to {result.get("next_agent")} - {result.get("reasoning")}'
            ]
        }