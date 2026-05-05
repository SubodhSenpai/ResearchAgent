from agents.base_agent import BaseAgent
from tools.web_search import search_web
from tools.document_retriever import retrieve_documents

RESEARCHER_PROMPTS = '''
You are a research specialist.
Your Job: given a query, identify the most important sub-questions and gather
raw information. Be thorough. Return what you found as structured bullet points. Include source URLS.
'''

class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__('Researcher', RESEARCHER_PROMPTS)

    def run(self, state: dict) -> dict:
        self._log(f'Researching: {state["query"]}')

        # Search the web
        search_results = search_web(state['query'])

        #Retrieve from vector store(RAG)
        rag_docs = retrieve_documents(state['query'])

        #Syntesise raw findings
        chain = self.build_chain(
            f'Query: {query}\n Search results: {results}\n RAG docs: {docs}'
        )
        summary = chain.invoke({
            'query': state['query'],
            'results': str(search_results[:3]),
            'docs': str(rag_docs[:2])
        })

        return {
            **state,
            'search_results': search_results,
            'documents': rag_docs,
            'messages': state['messages'] + [f'Researcher: {summary.content}']
        }