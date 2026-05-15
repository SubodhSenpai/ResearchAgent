from agents.base_agent import BaseAgent
from tools.memory_retrieval import MemoryRetrievalTool
import logging

logger = logging.getLogger(__name__)

ANALYST_PROMPT = '''You are a senior research analyst performing deep synthesis of multi-source research data.
Your role is to transform raw search results into a rigorous, well-structured analysis.

Given the search results, documents, and any prior critique feedback, you must:

1. **Cross-reference sources** — compare claims across multiple sources for consistency
2. **Identify patterns** — find recurring themes, trends, and consensus across sources
3. **Evaluate evidence strength** — distinguish strong evidence from speculation or opinion
4. **Synthesize a coherent narrative** — organize findings into a logical, flowing analysis
5. **Highlight contradictions** — note where sources disagree and provide context
6. **Address critique feedback** — if prior critique exists, specifically address the issues raised
7. **Identify remaining gaps** — clearly list what questions remain unanswered

Structure your analysis with clear sections:

## Executive Summary
(2-3 sentence overview of key findings)

## Detailed Analysis
(Organized by sub-topic with evidence from multiple sources)

## Cross-Source Validation
(Where sources agree/disagree, evidence strength assessment)

## Conclusions
(Well-supported conclusions drawn from the evidence)

## Remaining Gaps
(Specific questions or areas that need more research)

Be precise, cite sources where possible, and maintain analytical rigor throughout.
Write for an intelligent, technical audience.'''


class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__('Analyst', ANALYST_PROMPT)

    def run(self, state: dict) -> dict:
        iteration = state.get('iteration', 0)
        self._log(f'Synthesizing findings (iteration {iteration})')

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

            # ── Dynamic Prompting Safeguard ──────────────────────
            web_search_enabled = state.get('web_search_enabled', True)
            strict_guideline = ""
            if not web_search_enabled:
                strict_guideline = (
                    "\nSTRICT SAFEGUARD: Web search is DISABLED. You MUST ONLY analyze the information provided in the "
                    "'Documents from Knowledge Base' section. Do NOT mention missing web sources or external facts. "
                    "Focus entirely on synthesizing the local documents.\n"
                )

            chain = self._build_chain(
                "{strict_guideline}\n\n"
                "{memory_context}\n\n"
                'Original Query: {query}\n\n'
                'Research Plan:\n{plan}\n\n'
                'Search queries executed: {sub_queries}\n\n'
                'Web search results ({num_results} total):\n{search_results}\n\n'
                'Knowledge base documents:\n{documents}\n\n'
                'Available sources for citation:\n{sources}\n\n'
                'Previous critique feedback (address these issues):\n{critique}\n\n'
                'Research gaps to address:\n{gaps}'
            )

            # Prepare inputs with MUCH higher data limits
            search_results = state.get('search_results', [])
            documents = state.get('documents', [])
            source_urls = state.get('source_urls', [])
            critique = state.get('critique', '')
            research_gaps = state.get('research_gaps', [])
            plan = state.get('plan', [])
            sub_queries = state.get('sub_queries', [])

            # Format search results — show up to 15 results, 800 chars each
            search_str = '\n\n'.join([
                f"[Source {i+1}] {r.get('title', 'Untitled')}\n"
                f"URL: {r.get('url', 'N/A')}\n"
                f"Content: {str(r.get('content', ''))[:800]}"
                for i, r in enumerate(search_results[:15])
            ]) if search_results else "No search results available."

            # Format documents — more generous limits
            docs_str = '\n\n'.join([
                f"[Document {i+1}]: {str(d)[:600]}"
                for i, d in enumerate(documents[:6])
            ]) if documents else "No documents available."

            # Format source URLs for citation reference
            sources_str = '\n'.join([
                f"[{i+1}] {s.get('title', 'Untitled')} — {s.get('url', 'N/A')}"
                for i, s in enumerate(source_urls[:15])
            ]) if source_urls else "No sources tracked."

            critique_str = critique if critique else "No prior critique — this is the first analysis pass."
            plan_str = '\n'.join([f"- {p}" for p in plan]) if plan else "No specific plan."
            sub_queries_str = ', '.join(sub_queries) if sub_queries else "Single query search"
            gaps_str = '\n'.join([f"- {g}" for g in research_gaps]) if research_gaps else "None identified."

            result = chain.invoke({
                'strict_guideline': strict_guideline,
                'memory_context': memory_context,
                'query': state['query'],
                'plan': plan_str,
                'sub_queries': sub_queries_str,
                'num_results': len(search_results),
                'search_results': search_str,
                'documents': docs_str,
                'sources': sources_str,
                'critique': critique_str,
                'gaps': gaps_str,
            })

            analysis_text = result.content
            summary = analysis_text[:250] + "..." if len(analysis_text) > 250 else analysis_text

            logger.info(f"Analysis completed (iteration {iteration}): {summary[:150]}")

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