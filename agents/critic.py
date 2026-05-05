from agents.base_agent import BaseAgent
from langchain_core.output_parsers import JsonOutputParser

CRITIC_PROMPT = '''
You are a rigorous fact-checker and quality reviewer.
Given a research query and an analyst's synthesis, your job is to:
1. Check factual accuracy - flag any unsupported claims
2. Identify logical gaps or missing perspectives
3. Assess the overall quality on a scale of 0.0 to 1.0
Output a JSON object with keys:
- critique: string - your detailed feedback
- quality_score: float - 0.0(poor) to 1.0(excellent)
- issues: list of strings - specific problems found (empty list if none)
Output ONLY valid JSON, no other text.
'''

class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__('Critic', CRITIC_PROMPT)
        self.parser = JsonOutputParser()

    def run(self, state: dict) -> dict:
        self._log(f'Critiquing analysis (iteration {state.get("iteration", 1)})')

        chain = self._build_chain(
            f'Query: {query}\nAnalysis to review: \n{anaysis}'
        ) | self.parser

        try:
            result = chain.invoke({
                'query': state['query'],
                'analysis': state.get('analysis', 'No analysis provided.')
            })
            critique = result.get('critique', 'No specific critique.')
            quality_score = float(result.get('quality_score', 0.5))
            quality_score = max(0.0, min(1.0, quality_score))

        except Exception as e:
            critique = f'Critic parsing error: {e}. Proceeding with neutral score.'
            quality_score = 0.5

        return{
            **state,
            'critique': critique,
            'quality_score': quality_score,
            'messages': state['messages'] + [f'Critic: score={quality_score:.2f} - {critique[:150]}...']
        }