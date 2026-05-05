from langchain_community.vectores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config.settings import settings
from pathlib import Path

_vectorstore = None

def get_vectorestore() -> Chroma:
    '''
    Lazy singleton - create only when first needed.
    '''

    global_vectorstore
    if _vectorestore is None:
        embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key)
        _vectorstore = Chroma(
            persist_directory=settings.chroma_persist_dir,
            embedding_function=embeddings
        )
        return _vectorstore

def retrieve_documents(query: str, k: int = 4) -> list[str]:
    '''
    Retrieve k most relevant documents for the query.
    '''
    store = get_vectorestore()
    results = store.similartiy_search(query, k=k)
    return [doc.page_content for doc in results]

def add_documents(texts: list[str], metadatas: list[dict] = None):
    '''Add new documents to the vector store.'''
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200
    )
    chunks = splitter.create_documnets(texts, metadatas=metadatas or [])
    store = get_vectorestore()
    store.add_documents(chunks)
    