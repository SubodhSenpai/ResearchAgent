from agents.base_agent import BaseAgent

WRITER_PROMPT = '''
You are a expert technical writer.
Given a research query, a synthesis, and a critic's feedback, produce a polished, well-structured final answer. The answer should:
 -  Directly address the user's original question
 - Be organised with clear sections (use markdown headers where helpful)
 - Cite key sources inline where available
 - End with a concise 'Key Takeaways' section (3-5 bullet points)
 Write for an intelligent, technical audience. Be thorough but concise.
 '''

class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__('Writer', WRITER_PROMPT)

    def run(self, state: dict) -> dict:
        self._log('Producing final answer')

        chain = self._build_chain(
            'Original query: {query}'
            '\nResearch plan: {plan}'
            '\nAnalyst synthesis: \n{analysis}'
            '\nCritic feedback: \n{critique}'
            '\nQuality score achieved: {quality_score}'
        )

        result = chain.invoke({
            'query': state['query'],
            'plan': state.get('analysis', 'No analysis available.')
            'analysis': state.get('analysis', 'No analysis available.')
            'critique': state.get('critique', 'No critique available.')
            'quality_score': state.get('quality_score', 0.0)
        })

        final_answer = result.content

        return{
            **state,
            'final_answer': final_answer,
            'messages': state['messages'] + ['Writer: Final answer produced.']
        }