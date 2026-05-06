from agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)

ANALYST_PROMPT = '''You are a senior research analyst synthesizing information for accuracy and insight.
Given raw search results and retrieved documents, your job is to:
1. Identify the most important facts and patterns from the evidence
2. Synthesize findings into a coherent, well-organized narrative
3. Draw logical, well-supported conclusions
4. Flag any gaps in evidence, contradictions, or areas needing more research
5. Organize your analysis with clear sections and bullet points where helpful

Be precise and cite sources where possible. Write for an intelligent, technical audience.
Your analysis will be reviewed for quality, so ensure all claims are well-supported by the evidence provided.
'''

class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__('Analyst', ANALYST_PROMPT)

    def run(self, state: dict) -> dict:
        iteration = state.get('iteration', 0)
        self._log(f'Synthesizing findings (iteration {iteration})')

        chain = self._build_chain(
            'Query: {query}\n\n'
            'Search results:\n{search_results}\n\n'
            'Retrieved documents:\n{documents}\n\n'
            'Previous critique (if any):\n{critique}'
        )

        try:
            # Prepare inputs, limiting data size
            search_results = state.get('search_results', [])[:5]
            documents = state.get('documents', [])[:3]
            critique = state.get('critique', '')

            # Format data for LLM
            search_str = '\n'.join([
                f"- {str(r)[:500]}" for r in search_results
            ]) if search_results else "No search results available."

            docs_str = '\n'.join([
                f"- {str(d)[:500]}" for d in documents
            ]) if documents else "No documents available."

            critique_str = critique if critique else "Not yet - this is the first pass."

            result = chain.invoke({
                'query': state['query'],
                'search_results': search_str,
                'documents': docs_str,
                'critique': critique_str
            })

            analysis_text = result.content
            summary = analysis_text[:200] + "..." if len(analysis_text) > 200 else analysis_text

            logger.info(f"Analysis completed (iteration {iteration}): {summary}")

            return {
                **state,
                'analysis': analysis_text,
                'messages': state['messages'] + [f'Analyst: {summary}']
            }

        except Exception as e:
            error_msg = f'Analyst error: {str(e)[:150]}'
            logger.error(error_msg)
            return {
                **state,
                'analysis': f"[Analysis failed: {str(e)[:100]}]",
                'messages': state['messages'] + [error_msg],
                'error': error_msg
            }