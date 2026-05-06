from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import settings

_vectorstore = None


def get_vectorstore() -> Chroma:
    """Lazy singleton — create only when first needed."""
    global _vectorstore
    if _vectorstore is None:
        embeddings = settings.get_embeddings()
        _vectorstore = Chroma(
            persist_directory=settings.chroma_rag_dir,
            embedding_function=embeddings,
        )
    return _vectorstore


def build_vector_store() -> Chroma:
    """Initialize and return the shared Chroma vector store."""
    return get_vectorstore()


def retrieve_documents(query: str, k: int = 4) -> list[str]:
    """Retrieve k most relevant documents for the query."""
    store = get_vectorstore()
    results = store.similarity_search(query, k=k)
    return [doc.page_content for doc in results]


def add_documents(texts: list[str], metadatas: list[dict] | None = None) -> None:
    """Add new documents to the vector store."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.create_documents(texts, metadatas=metadatas or [])
    store = get_vectorstore()
    store.add_documents(chunks)
