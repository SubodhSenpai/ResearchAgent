from agents.base_agent import BaseAgent
from tools.web_search import search_web_multi
from tools.document_retriever import retrieve_documents
from tools.memory_retrieval import MemoryRetrievalTool
import logging

logger = logging.getLogger(__name__)

RESEARCHER_PROMPT = '''You are a thorough research specialist. Your job is to gather comprehensive, 
high-quality information from multiple angles for the user's research query.

Given the search results and documents provided, synthesize a detailed research summary that:

1. **Extracts key facts** — specific data points, statistics, dates, names, and figures
2. **Identifies multiple perspectives** — cover different viewpoints and interpretations
3. **Notes source quality** — distinguish between authoritative sources vs. opinions
4. **Flags gaps** — explicitly mention what information is missing or couldn't be found
5. **Preserves source attribution** — always mention which source each fact comes from
6. **Builds on prior research** — incorporate relevant context from past research sessions

Structure your response as:
## Key Findings
(Bullet points of main facts with source attribution)

## Detailed Evidence
(Organized by sub-topic with evidence from sources)

## Source Assessment
(Brief evaluation of source quality and reliability)

## Information Gaps
(What's still unknown or needs further investigation)

Be thorough, precise, and evidence-based. Never fabricate information.
'''


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__('Researcher', RESEARCHER_PROMPT)

    def run(self, state: dict) -> dict:
        iteration = state.get('iteration', 0)
        user_id = state.get('user_id')
        self._log(f'Gathering research (iteration {iteration}): {state["query"][:60]}...')

        try:
            # Get memory context for this user
            memory_context = ""
            try:
                from auth.database import SessionLocal
                if user_id:
                    db = SessionLocal()
                    memory_tool = MemoryRetrievalTool(user_id, db)
                    memory_context = memory_tool.get_researcher_context(state.get('query', ''))
                    db.close()
            except Exception as e:
                logger.debug(f"Could not retrieve memory context: {e}")

            # ── Build search queries ──────────────────────────────
            # Use sub-queries from supervisor if available, otherwise use the raw query
            sub_queries = state.get('sub_queries', [])
            research_gaps = state.get('research_gaps', [])

            # Always include the main query
            search_queries = [state['query']]

            # Add supervisor-generated sub-queries
            if sub_queries:
                search_queries.extend(sub_queries[:4])  # Cap at 4 additional sub-queries

            # If critic identified gaps, create targeted follow-up searches
            if research_gaps:
                for gap in research_gaps[:3]:  # Max 3 gap-filling searches
                    gap_query = f"{state['query']} {gap}"
                    search_queries.append(gap_query)
                logger.info(f"Added {min(len(research_gaps), 3)} gap-filling searches: {research_gaps[:3]}")

            # Deduplicate queries (case-insensitive)
            seen = set()
            unique_queries = []
            for q in search_queries:
                q_lower = q.strip().lower()
                if q_lower not in seen:
                    seen.add(q_lower)
                    unique_queries.append(q.strip())

            # Cap total queries to avoid excessive API usage
            unique_queries = unique_queries[:6]

            logger.info(f"Executing {len(unique_queries)} search queries: {[q[:50] for q in unique_queries]}")

            # ── Execute multi-query search ────────────────────────
            search_results, source_urls = search_web_multi(unique_queries, max_results_per_query=5)

            # Merge with existing results (for follow-up searches) - NEW FIRST
            existing_results = state.get('search_results', [])
            existing_urls = state.get('source_urls', [])
            
            all_results = []
            seen_urls = set()
            
            # Prioritize NEW results so gap-filling queries don't get truncated out
            for r in search_results + existing_results:
                url = r.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
                elif not url:
                    all_results.append(r)

            all_urls = existing_urls.copy()
            existing_url_set = {u.get('url', '') for u in existing_urls}
            for u in source_urls:
                if u.get('url', '') not in existing_url_set:
                    all_urls.append(u)
                    existing_url_set.add(u['url'])

            logger.info(f"Total: {len(all_results)} results, {len(all_urls)} unique sources")

            # ── Retrieve from PageIndex RAG (hierarchical, OCR-enabled) ──────────────────
            logger.info("Retrieving documents from PageIndex knowledge base")
            rag_docs = []
            seen_docs = set()
            for q in unique_queries[:3]:  # Search for main + top sub-queries
                docs = retrieve_documents(q, user_id=str(user_id) if user_id else "", k=3)
                for d in docs:
                    if d not in seen_docs:
                        seen_docs.add(d)
                        rag_docs.append(d)
            logger.info(f"Retrieved {len(rag_docs)} unique document sections from PageIndex")

            # Format chat history
            chat_history = state.get('chat_history', [])
            chat_history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history]) if chat_history else "No previous history."

            # ── Synthesize with LLM ──────────────────────────────
            chain = self._build_chain(
                "{memory_context}\n\n"
                "Chat History (Previous turns in this session):\n{chat_history}\n\n"
                "Current Query: {query}\n\n"
                "Search queries executed: {search_queries}\n\n"
                "Web search results ({num_results} total):\n{results}\n\n"
                "Documents from knowledge base:\n{docs}\n\n"
                "Research gaps to fill (from previous critique):\n{gaps}"
            )

            # Format search results — show MORE data to the LLM (up to 12 results, 800 chars each)
            search_str = '\n\n'.join([
                f"[Source {i+1}] {r.get('title', 'Untitled')}\n"
                f"URL: {r.get('url', 'N/A')}\n"
                f"Content: {str(r.get('content', ''))[:800]}"
                for i, r in enumerate(all_results[:12])
            ]) if all_results else "No search results available."

            docs_str = '\n\n'.join([
                f"[Document {i+1}]: {str(d)[:600]}"
                for i, d in enumerate(rag_docs[:6])
            ]) if rag_docs else "No documents available."

            gaps_str = '\n'.join([f"- {g}" for g in research_gaps]) if research_gaps else "No specific gaps identified yet."

            result = chain.invoke({
                'memory_context': memory_context,
                'chat_history': chat_history_str,
                'query': state['query'],
                'search_queries': ', '.join(unique_queries),
                'num_results': len(all_results),
                'results': search_str,
                'docs': docs_str,
                'gaps': gaps_str,
            })

            summary = result.content
            summary_preview = summary[:200] + "..." if len(summary) > 200 else summary
            logger.info(f"Research summary: {summary_preview}")

            return {
                **state,
                'search_results': all_results,
                'source_urls': all_urls,
                'sub_queries': unique_queries,
                'documents': rag_docs,
                'messages': state['messages'] + [f'Researcher: Gathered {len(all_results)} results from {len(unique_queries)} queries. {summary_preview}']
            }

        except Exception as e:
            error_msg = f'Research error: {str(e)[:150]}'
            logger.error(error_msg)
            return {
                **state,
                'search_results': state.get('search_results', []),
                'source_urls': state.get('source_urls', []),
                'documents': state.get('documents', []),
                'messages': state['messages'] + [error_msg],
                'error': error_msg
            }