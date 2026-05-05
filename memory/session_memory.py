import uuid
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config.settings import settings


class SessionMemory:
    '''
    Persists research findings across sessions using ChromaDB.
    Stores: query, final_answer, quality_score, and source documents.

    Archtecture note: chunk_size=1000, overlap=200 mirrors the openAI embeddings config shown in the Memory Layer of the architecture.
    '''

    COLLECTION_NAME = 'research_sessions'

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
            )
        
        # self._embeddings = OpenAIEmbeddings(model='text-embeddings-3-small', api_key=settings.open_api_key)
        self._embeddings = GoogleGenerativeAIEmbeddings(model=settings.model_name)
        
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={'hnsw:space': 'cosine'}
        )

    def save_session(self, query: str, answer: str, quality_score: float, documents: list[str] | None = None):
        '''Persist a completed research session. Return the session id. '''
        session_id = str(uuid.uuid4())
        combined_text = f'QUERY: {query}\nANSWER: {answer}'
        embedding = self._embeddings.embed_query(combined_text)
        self._collection.add(
            ids=[session_id],
            embeddings=[embedding],
            documents=[combined_text],
            metadatas=[{
                'query': query,
                'answer': answer,
                'quality_score': str(quality_score),
                'source_count': str(len(documents or []))
            }]
        )
        return session_id

    def retrieve_similar(self, query: str, k: int = 4) -> list[dict]:
        '''
        Return up to k past sessions whose answers are semantically 
        similar to the current query. Mirrors similartiy_search(query,k)
        shown in the architecture diagram.
        '''

        if self._collection.count() == 0:
            return []

        embedding = self._embeddings.embed_query(query)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(k, self._collection.count()),
            include=['documents', 'metadatas', 'distances']
        )

        sessions = []

        for doc, meta, dist in zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ):
            sessions.append({
                'text': doc,
                'query': meta.get('query', ''),
                'answer': meta.get('answer', ''),
                'quality_score': float(meta.get('quality_score', 0)),
                'similarity': round(1-dist, 4)   #Cosine distance -> similarity
            })

        return sessions

    def is_cache_hit(self, query: str, threshold: float = 0.92) -> str | None:
        ''' 
        Return an cached answer if a near-identical query was already answered at the high quality.
        Prevents redundant LLM calls for repeat questions.
        '''
        results = self.retrieve_similar(query, k=1)

        if results and results[0]['similarity'] >= threshold:
            score = results[0]['quality_score']
            if score >= settings.quality_threshold:
                return results[0]['answer']
        return None

    def count(self) -> int:
        '''Return the number of persisted sessions.'''
        return self._collection.count()

    def clear(self) -> None:
        '''Delete all stored sessions (useful in testing).'''
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={'hnsw:space': 'cosine'}
        )