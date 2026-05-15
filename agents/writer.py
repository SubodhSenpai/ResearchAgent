from agents.base_agent import BaseAgent
from tools.memory_retrieval import MemoryRetrievalTool
import logging

logger = logging.getLogger(__name__)

WRITER_PROMPT = '''You are an expert technical writer producing a comprehensive, publication-quality research report.
Your role is to synthesize all research findings into a polished, well-structured response.

Guidelines:
1. **Direct Answer** — Open with a clear, direct answer to the user's query (2-3 sentences)
2. **Structured Sections** — Use markdown headers (##, ###) for clear organization
3. **Evidence-Based** — Every major claim MUST cite its source using [Source N] format
4. **Multiple Perspectives** — Present different viewpoints where they exist
5. **Depth & Nuance** — Go beyond surface-level; provide genuine insight and analysis
6. **Data & Specifics** — Include specific numbers, dates, statistics where available
7. **Source Citations** — Include a "Sources" section at the end listing all referenced URLs
8. **Key Takeaways** — End with 4-6 bullet points summarizing the most important findings
9. **Limitations** — Acknowledge any limitations or areas of uncertainty
10. **Consistency** — Match the depth and style of previous research on similar topics

Your response should feel like a well-researched article, not a generic AI summary.
Aim for comprehensive coverage (800-1500 words for complex topics, 400-800 for simpler ones).
Use the analyst's synthesis and critic's feedback to ensure quality and accuracy.
ALWAYS include the Sources section with actual URLs from the source list provided.'''


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__('Writer', WRITER_PROMPT)

    def run(self, state: dict) -> dict:
        self._log('Composing final answer')

        try:
            # Get memory context for this user
            memory_context = ""
            try:
                from auth.database import SessionLocal
                user_id = state.get('user_id')
                if user_id:
                    db = SessionLocal()
                    memory_tool = MemoryRetrievalTool(user_id, db)
                    memory_context = memory_tool.get_relevant_context(state.get('query', ''), context_type='recent')
                    db.close()
            except Exception as e:
                logger.debug(f"Could not retrieve memory context: {e}")

            # Format chat history
            chat_history = state.get('chat_history', [])
            chat_history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history]) if chat_history else "No previous history."

            chain = self._build_chain(
                "{memory_context}\n\n"
                "Chat History (Previous turns in this session):\n{chat_history}\n\n"
                'Current Query:\n{query}\n\n'
                'Research Plan:\n{plan}\n\n'
                'Sub-queries investigated:\n{sub_queries}\n\n'
                'Analyst\'s Synthesis:\n{analysis}\n\n'
                'Quality Assessment:\n{critique}\n\n'
                'Quality Score: {quality_score:.2f}/1.0\n\n'
                'Available Sources for Citation (USE THESE URLs):\n{sources}\n\n'
                'Raw search highlights (for additional detail):\n{search_highlights}'
            )

            # Prepare inputs
            plan_text = '\n'.join([f"- {p}" for p in state.get('plan', [])]) or "No specific plan"
            sub_queries_text = '\n'.join([f"- {q}" for q in state.get('sub_queries', [])]) or "Single query"
            analysis = state.get('analysis', 'No analysis available.')
            critique = state.get('critique', 'No critique available.')
            quality_score = float(state.get('quality_score', 0.0))

            # Format source URLs for proper citation
            source_urls = state.get('source_urls', [])
            sources_str = '\n'.join([
                f"[{i+1}] {s.get('title', 'Untitled')} — {s.get('url', 'N/A')}"
                for i, s in enumerate(source_urls[:20])
            ]) if source_urls else "No sources available."

            # Include search result highlights for additional context
            search_results = state.get('search_results', [])
            highlights_str = '\n\n'.join([
                f"[Source {i+1}] {r.get('title', 'Untitled')}\n"
                f"URL: {r.get('url', 'N/A')}\n"
                f"{str(r.get('content', ''))[:600]}"
                for i, r in enumerate(search_results[:10])
            ]) if search_results else "No search results."

            result = chain.invoke({
                'memory_context': memory_context,
                'chat_history': chat_history_str,
                'query': state['query'],
                'plan': plan_text,
                'sub_queries': sub_queries_text,
                'analysis': analysis,
                'critique': critique,
                'quality_score': quality_score,
                'sources': sources_str,
                'search_highlights': highlights_str,
            })

            final_answer = result.content
            logger.info(f"Final answer composed ({len(final_answer)} chars, quality={quality_score:.2f})")

            return {
                **state,
                'final_answer': final_answer,
                'messages': state['messages'] + [f'Writer: Final answer composed ({len(final_answer)} chars).']
            }

        except Exception as e:
            error_msg = f'Writer error: {str(e)[:100]}'
            logger.error(error_msg)

            # Fallback answer with available data
            source_urls = state.get('source_urls', [])
            sources_section = '\n'.join([
                f"- [{s.get('title', 'Source')}]({s.get('url', '')})"
                for s in source_urls[:10]
            ]) if source_urls else "*No sources available*"

            fallback_answer = (
                f"# Research Report\n\n"
                f"**Query:** {state['query']}\n\n"
                f"## Analysis\n\n"
                f"{state.get('analysis', 'Unable to generate analysis')[:1000]}\n\n"
                f"## Quality Assessment\n\n"
                f"Score: {state.get('quality_score', 0.0):.2f}/1.0\n\n"
                f"## Sources\n\n{sources_section}\n\n"
                f"---\n*Note: Final composition encountered an error. "
                f"The above reflects raw research findings.*"
            )

            return {
                **state,
                'final_answer': fallback_answer,
                'messages': state['messages'] + [error_msg],
                'error': error_msg
            }