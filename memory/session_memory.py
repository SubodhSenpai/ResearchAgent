import uuid
import chromadb
from chromadb.config import Settings as ChromaSettings
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
            path=settings.chroma_sessions_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
            )
        
        self._embeddings = settings.get_embeddings()
        
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={'hnsw:space': 'cosine'}
        )

    def save_session(
        self,
        session_id: str,
        user_id: str,
        query: str,
        answer: str,
        quality_score: float,
        timestamp: str,
        documents: list[str] | None = None
    ):
        '''Persist a completed research session with full session/user context.'''
        combined_text = f'QUERY: {query}\nANSWER: {answer}'
        embedding = self._embeddings.embed_query(combined_text)
        self.collection.add(
            ids=[session_id],
            embeddings=[embedding],
            documents=[combined_text],
            metadatas=[{
                'session_id': session_id,
                'user_id': user_id,
                'query': query,
                'answer': answer,
                'quality_score': str(quality_score),
                'timestamp': timestamp,
                'source_count': str(len(documents or []))
            }]
        )

    def retrieve_similar(self, query: str, user_id: str, k: int = 4) -> list[dict]:
        '''
        Return up to k past sessions whose answers are semantically
        similar to the current query, filtered by user_id for isolation.
        '''

        if self.collection.count() == 0:
            return []

        embedding = self._embeddings.embed_query(query)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(k, self.collection.count()),
            where={"user_id": {"$eq": user_id}},
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
                'session_id': meta.get('session_id', ''),
                'query': meta.get('query', ''),
                'answer': meta.get('answer', ''),
                'quality_score': float(meta.get('quality_score', 0)),
                'timestamp': meta.get('timestamp', ''),
                'similarity': round(1-dist, 4)
            })

        return sessions

    def is_cache_hit(self, query: str, user_id: str, threshold: float = 0.92) -> str | None:
        '''
        Return a cached answer if a near-identical query was already answered at high quality,
        filtered to the specific user for memory isolation.
        '''
        results = self.retrieve_similar(query, user_id=user_id, k=1)

        if results and results[0]['similarity'] >= threshold:
            score = results[0]['quality_score']
            if score >= settings.quality_threshold:
                return results[0]['answer']
        return None

    def count(self) -> int:
        '''Return the number of persisted sessions.'''
        return self.collection.count()

    def clear(self) -> None:
        '''Delete all stored sessions (useful in testing).'''
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={'hnsw:space': 'cosine'}
        )