from agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)

WRITER_PROMPT = '''You are an expert technical writer synthesizing research findings into a comprehensive final answer.
Your role is to produce a polished, well-structured response that directly addresses the user's query.

Guidelines for your response:
1. **Structure**: Organize with clear markdown headers (##, ###) for readability
2. **Directness**: Answer the original question directly in the opening paragraph
3. **Evidence**: Cite sources and data from the research where available
4. **Clarity**: Use clear language appropriate for an intelligent, technical audience
5. **Completeness**: Address all aspects of the query, including nuances and context
6. **Takeaways**: End with a "Key Takeaways" section (3-5 bullet points summarizing the answer)

Consider the analyst's synthesis, critic's feedback, and quality score in crafting your response.
Ensure accuracy and acknowledge any limitations or areas of uncertainty.
Be thorough but concise - avoid unnecessary verbosity.
'''

class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__('Writer', WRITER_PROMPT)

    def run(self, state: dict) -> dict:
        self._log('Composing final answer')

        chain = self._build_chain(
            'Original Query:\n{query}\n\n'
            'Research Plan:\n{plan}\n\n'
            'Analyst\'s Synthesis:\n{analysis}\n\n'
            'Quality Assessment:\n{critique}\n\n'
            'Quality Score: {quality_score:.2f}/1.0'
        )

        try:
            # Prepare all inputs safely
            plan_text = '\n'.join([f"- {p}" for p in state.get('plan', [])]) or "No specific plan"
            analysis = state.get('analysis', 'No analysis available.')
            critique = state.get('critique', 'No critique available.')
            quality_score = float(state.get('quality_score', 0.0))

            result = chain.invoke({
                'query': state['query'],
                'plan': plan_text,
                'analysis': analysis,
                'critique': critique,
                'quality_score': quality_score
            })

            final_answer = result.content
            logger.info(f"Final answer composed ({len(final_answer)} chars, quality={quality_score:.2f})")

            return {
                **state,
                'final_answer': final_answer,
                'messages': state['messages'] + ['Writer: Final answer composed.']
            }

        except Exception as e:
            error_msg = f'Writer error: {str(e)[:100]}'
            logger.error(error_msg)

            # Fallback answer
            fallback_answer = (
                f"# Answer\n\n"
                f"**Query:** {state['query']}\n\n"
                f"**Analysis Summary:** {state.get('analysis', 'Unable to generate analysis')[:500]}\n\n"
                f"**Quality Assessment:** {state.get('quality_score', 0.0):.2f}/1.0\n\n"
                f"*Note: Final composition encountered an error, but above information reflects research findings.*"
            )

            return {
                **state,
                'final_answer': fallback_answer,
                'messages': state['messages'] + [error_msg],
                'error': error_msg
            }