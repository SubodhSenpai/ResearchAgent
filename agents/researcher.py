from agents.base_agent import BaseAgent
from tools.web_search import search_web
from tools.document_retriever import retrieve_documents
import logging

logger = logging.getLogger(__name__)

RESEARCHER_PROMPTS = '''You are a thorough research specialist gathering information for complex queries.
Your job is to:
1. Conduct comprehensive web search to find relevant information
2. Identify key facts, perspectives, and authoritative sources
3. Retrieve supporting documents from the knowledge base
4. Summarize findings in structured format
5. Note any gaps or uncertainties in the data

Be thorough but focus on high-quality, authoritative sources.
Always try to provide multiple perspectives on the topic.
Include source URLs and citations where available.
'''

class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__('Researcher', RESEARCHER_PROMPTS)

    def run(self, state: dict) -> dict:
        iteration = state.get('iteration', 0)
        self._log(f'Gathering research (iteration {iteration}): {state["query"][:60]}...')

        try:
            # Search the web (cap at 10 results to avoid memory bloat)
            logger.info(f"Searching web for: {state['query']}")
            search_results = search_web(state['query'], max_results=10)[:10]
            logger.info(f"Found {len(search_results)} web results")

            # Retrieve from vector store (RAG)
            logger.info("Retrieving documents from knowledge base")
            rag_docs = retrieve_documents(state['query'], k=5)
            logger.info(f"Retrieved {len(rag_docs)} documents")

            # Synthesize raw findings
            chain = self._build_chain(
                "Query: {query}\n\n"
                "Search results found:\n{results}\n\n"
                "Documents from knowledge base:\n{docs}"
            )

            # Format data for LLM (with limits)
            search_str = '\n'.join([
                f"- {str(r)[:300]}" for r in search_results[:3]
            ]) if search_results else "No search results available."

            docs_str = '\n'.join([
                f"- {str(d)[:300]}" for d in rag_docs[:2]
            ]) if rag_docs else "No documents available."

            result = chain.invoke({
                'query': state['query'],
                'results': search_str,
                'docs': docs_str
            })

            summary = result.content
            summary_preview = summary[:150] + "..." if len(summary) > 150 else summary
            logger.info(f"Research summary: {summary_preview}")

            return {
                **state,
                'search_results': search_results,
                'documents': rag_docs,
                'messages': state['messages'] + [f'Researcher: {summary_preview}']
            }

        except Exception as e:
            error_msg = f'Research error: {str(e)[:100]}'
            logger.error(error_msg)
            return {
                **state,
                'search_results': [],
                'documents': [],
                'messages': state['messages'] + [error_msg],
                'error': error_msg
            }