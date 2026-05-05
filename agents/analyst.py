from agents.base_agent import BaseAgent

ANALYST_PROMPT = '''
You are a senior research analyst.
Given raw search results and retrieved documents, your job is to:
1. Identify the most important facts and patterns
2. Synthesise findings into a coherent narrative
3. Draw well-supported conclusions
4. Flag any gaps or contradictions in the evidence
Be prcise. Cite sources where possible. Write in clear prose.
'''

class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__('Analyst', ANALYST_PROMPT)

    def run(self, state: dict) -> dict:
        self._log(f'Analysing: finding for: {state["query"]}')

        chain = self._build_chain(
            f'Query: {query}'
            '\nSearch results: {search_results}'
            '\nRetrieved documents: {documents}'
            '\nPrevious critique (if any): critique'
        )

        result = chain.invoke({
            'query': state['query'],
            'search_results': str(state.get('search_results', [])[:5]),
            'documents': str(state.get('documents', [])[:3]),
            'critique': state.get('critique', 'Not yet - this is the first pass.')
        })

        analysis_text = result.content

        return{
            **state,
            'analysis': analysis_text,
            'messages': state['messages'] + [f'Analyst: analysis_text[:200]']
        }