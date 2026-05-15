from agents.base_agent import BaseAgent
from langchain_core.output_parsers import JsonOutputParser
from tools.memory_retrieval import MemoryRetrievalTool
import logging

logger = logging.getLogger(__name__)

CRITIC_PROMPT = '''You are a rigorous fact-checker and quality assurance specialist for research synthesis.
Given a research query and an analyst's synthesis, perform a thorough quality evaluation.

Your evaluation must assess:
1. **Factual accuracy** — Are claims supported by the provided sources? Flag unsupported assertions.
2. **Logical coherence** — Is the reasoning sound? Are there logical gaps or non-sequiturs?
3. **Completeness** — Does the analysis fully address ALL aspects of the original query?
4. **Evidence strength** — Are conclusions well-supported, or based on weak/single sources?
5. **Source diversity** — Does the analysis draw from multiple independent sources?
6. **Depth** — Is the analysis superficial or does it provide genuine insight?

CRITICAL: You must also identify specific RESEARCH GAPS — concrete topics or questions that 
the researcher should investigate in a follow-up search to improve the analysis quality.

Output a JSON object with these exact keys:
- critique: string — your detailed feedback (3-5 sentences covering strengths and weaknesses)
- quality_score: float — overall quality from 0.0 (poor) to 1.0 (excellent)
- strengths: list of strings — 2-4 specific things done well
- issues: list of strings — specific problems found (empty list [] if none)
- research_gaps: list of strings — 1-3 specific topics/questions to search for in follow-up research (empty list [] if analysis is thorough)
- recommendation: string — one of ["needs_more_research", "needs_reanalysis", "ready_to_write"]

Quality scoring guide:
- 0.0-0.3: Largely inaccurate, unsupported claims, major gaps in coverage
- 0.4-0.6: Some accurate information but significant gaps, weak evidence, or missing perspectives
- 0.7-0.85: Good quality — well-supported, covers main aspects, minor gaps acceptable
- 0.85-1.0: Excellent — comprehensive, multi-source evidence, addresses query fully with depth

Be strict but fair. A score of 0.7+ means the analysis is genuinely useful and well-evidenced.
Output ONLY valid JSON, no other text.'''


class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__('Critic', CRITIC_PROMPT)
        self.parser = JsonOutputParser()

    def run(self, state: dict) -> dict:
        iteration = state.get('iteration', 1)
        self._log(f'Evaluating analysis quality (iteration {iteration})')

        try:
            # Get memory context for this user
            memory_context = ""
            try:
                from auth.database import SessionLocal
                user_id = state.get('user_id')
                if user_id:
                    db = SessionLocal()
                    memory_tool = MemoryRetrievalTool(user_id, db)
                    memory_context = memory_tool.get_analyst_context(state.get('query', ''))
                    db.close()
            except Exception as e:
                logger.debug(f"Could not retrieve memory context: {e}")

            chain = self._build_chain(
                "{memory_context}\n\n"
                'Original Query: {query}\n\n'
                'Number of sources searched: {num_sources}\n\n'
                'Source URLs available:\n{source_list}\n\n'
                'Analysis to evaluate:\n{analysis}'
            ) | self.parser

            # Provide source context so critic can assess source diversity
            source_urls = state.get('source_urls', [])
            source_list = '\n'.join([
                f"[{i+1}] {s.get('title', 'Untitled')} — {s.get('url', 'N/A')}"
                for i, s in enumerate(source_urls[:15])
            ]) if source_urls else "No source tracking available."

            result = chain.invoke({
                'memory_context': memory_context,
                'query': state['query'],
                'num_sources': len(source_urls),
                'source_list': source_list,
                'analysis': state.get('analysis', 'No analysis provided.')
            })

            # Extract and validate quality score
            try:
                quality_score = float(result.get('quality_score', 0.5))
            except (ValueError, TypeError):
                quality_score = 0.5
                logger.warning(f"Invalid quality_score format: {result.get('quality_score')}")

            quality_score = max(0.0, min(1.0, quality_score))

            critique = result.get('critique', 'Analysis reviewed.')
            issues = result.get('issues', [])
            strengths = result.get('strengths', [])
            research_gaps = result.get('research_gaps', [])
            recommendation = result.get('recommendation', 'ready_to_write')

            # Validate recommendation
            if recommendation not in ('needs_more_research', 'needs_reanalysis', 'ready_to_write'):
                recommendation = 'ready_to_write' if quality_score >= 0.7 else 'needs_reanalysis'

            # Create informative message
            message = (
                f'Critic: score={quality_score:.2f}, recommendation={recommendation} — {critique[:200]}'
            )
            logger.info(f"Critique (iteration {iteration}): {message}")

            if issues:
                logger.warning(f"Issues identified: {', '.join(issues[:3])}")
            if research_gaps:
                logger.info(f"Research gaps for follow-up: {', '.join(research_gaps[:3])}")

            return {
                **state,
                'critique': critique,
                'quality_score': quality_score,
                'research_gaps': research_gaps,
                '_critic_recommendation': recommendation,
                'messages': state['messages'] + [message]
            }

        except Exception as e:
            error_msg = f'Critic parsing error: {str(e)[:100]}'
            logger.error(error_msg)

            return {
                **state,
                'critique': error_msg,
                'quality_score': 0.5,
                'research_gaps': [],
                '_critic_recommendation': 'ready_to_write',
                'messages': state['messages'] + [f'Critic: {error_msg}'],
            }