from agents.base_agent import BaseAgent
from langchain_core.output_parsers import JsonOutputParser
import logging

logger = logging.getLogger(__name__)

CRITIC_PROMPT = '''You are a rigorous fact-checker and quality assurance specialist for research synthesis.
Given a research query and an analyst's synthesis, evaluate the quality and completeness.

Your evaluation should assess:
1. Factual accuracy - flag any claims that appear unsupported or questionable
2. Logical coherence - identify gaps, contradictions, or missing perspectives
3. Completeness - determine if the analysis adequately addresses the original query
4. Evidence strength - evaluate whether conclusions are well-supported by sources

Output a JSON object with keys:
- critique: string - your detailed feedback (2-4 sentences)
- quality_score: float - overall quality rating from 0.0 (poor) to 1.0 (excellent)
- strengths: list of strings - what the analysis does well
- issues: list of strings - specific problems found (empty if none)

Quality scoring guide:
- 0.0-0.3: Inaccurate, unsupported claims, major gaps
- 0.4-0.6: Some accurate information but with gaps or weak evidence
- 0.7-0.85: Good quality, well-supported, minor gaps possible
- 0.9-1.0: Excellent - comprehensive, well-evidenced, addresses query fully

Output ONLY valid JSON, no other text.
'''

class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__('Critic', CRITIC_PROMPT)
        self.parser = JsonOutputParser()

    def run(self, state: dict) -> dict:
        iteration = state.get('iteration', 1)
        self._log(f'Evaluating analysis quality (iteration {iteration})')

        chain = self._build_chain(
            'Original Query: {query}\n\n'
            'Analysis to evaluate:\n{analysis}'
        ) | self.parser

        try:
            result = chain.invoke({
                'query': state['query'],
                'analysis': state.get('analysis', 'No analysis provided.')
            })

            # Extract and validate quality score
            try:
                quality_score = float(result.get('quality_score', 0.5))
            except (ValueError, TypeError):
                quality_score = 0.5
                logger.warning(f"Invalid quality_score format: {result.get('quality_score')}")

            # Clamp score to valid range
            quality_score = max(0.0, min(1.0, quality_score))

            critique = result.get('critique', 'Analysis reviewed.')
            issues = result.get('issues', [])
            strengths = result.get('strengths', [])

            # Create informative message
            message = f'Critic: score={quality_score:.2f} - {critique[:150]}'
            logger.info(f"Critique (iteration {iteration}): {message}")

            if issues:
                logger.warning(f"Issues identified: {', '.join(issues[:3])}")

            return {
                **state,
                'critique': critique,
                'quality_score': quality_score,
                'messages': state['messages'] + [message]
            }

        except Exception as e:
            error_msg = f'Critic parsing error: {str(e)[:80]}'
            logger.error(error_msg)

            # On parsing error, assign a conservative quality score
            quality_score = 0.5

            return {
                **state,
                'critique': error_msg,
                'quality_score': quality_score,
                'messages': state['messages'] + [f'Critic: {error_msg}'],
            }