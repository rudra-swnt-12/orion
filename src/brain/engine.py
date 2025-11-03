import logging
import sys
import os
from dotenv import load_dotenv
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings
from llama_index.core.node_parser import HierarchicalNodeParser
from llama_index.core.node_parser import get_leaf_nodes
from llama_index.llms.groq import Groq
from llama_index.core import Settings

load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

KNOWLEDGE_DIR = "./knowledge_base"
INDEX_PERSIST_DIR = "./storage/brain_index" # To save the index
LLM_MODEL = "llama-3.1-8b-instant"

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)

try:
    log.info(f"Setting up LLM: Groq ({LLM_MODEL})")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found. Please add it to your .env file.")
    Settings.llm = Groq(
        model=LLM_MODEL,
        api_key=GROQ_API_KEY,
        request_timeout=120.0
    )

    log.info("Setting up embedding model: BAAI/bge-small-en-v1.5")
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-small-en-v1.5"
    )

except Exception as e:
    log.error(f"Failed to setup LLM/Embeddings.")
    log.error(f"Error: {e}")
    sys.exit(1)

def build_index():
    log.info(f"Starting to build index from: {KNOWLEDGE_DIR}")
    documents = SimpleDirectoryReader(KNOWLEDGE_DIR, recursive=True).load_data()
    if not documents:
        log.error("No documents found. Did you add files to /knowledge_base?")
        return
    log.info(f"Loaded {len(documents)} document(s).")

    # This is the "Hierarchical RAG" part.
    # It creates small chunks (128), medium chunks (512), and large chunks (1024)
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[1024, 512, 128]
    )
    nodes = node_parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes) # The smallest nodes for vector search
    
    log.info(f"Created {len(nodes)} total nodes and {len(leaf_nodes)} leaf nodes.")

    # Built the vector index only from the smallest (leaf) nodes
    docstore = SimpleDocumentStore()
    storage_context = StorageContext.from_defaults(docstore=docstore)
    index = VectorStoreIndex(leaf_nodes, storage_context=storage_context)
    storage_context.docstore.add_documents(nodes)

    # Save the index to disk so we don't have to rebuild it every time
    index.storage_context.persist(persist_dir=INDEX_PERSIST_DIR)
    log.info(f"Index built and saved to: {INDEX_PERSIST_DIR}")
    return index

def get_query_engine():
    try:
        # Load the index from disk
        storage_context = StorageContext.from_defaults(persist_dir=INDEX_PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        log.info(f"Loaded existing index from: {INDEX_PERSIST_DIR}")
    except FileNotFoundError:
        log.warning("Index not found. Building a new one...")
        index = build_index()
    if index is None:
        log.error("Failed to load or build index.")
        return None

    # This creates a "retriever" that automatically finds the small
    # chunk and then "merges" it with its parent chunks for more context.
    query_engine = index.as_query_engine(
        similarity_top_k=3,
        # This AutoMergingRetriever is what makes it hierarchical
        retriever_mode="Recursive", 
    )
    return query_engine

if __name__ == "__main__":
    # This block only runs when you execute the file directly
    log.info("Running Brain Engine in standalone test mode...")
    if not GROQ_API_KEY:
        log.error("GROQ_API_KEY not found. Please create a .env file and add it.")
        sys.exit(1)
    else:
        log.info("GROQ_API_KEY loaded successfully.")
    query_engine = get_query_engine()

    if query_engine:
        log.info("Query Engine is ready. Type your questions (or 'quit' to exit).")

        # Test with a high-level question
        print("\n--- Test 1: High-level question ---")
        question1 = "What are the common causes of a database connection limit?"
        print(f"Query: {question1}")
        response1 = query_engine.query(question1)
        print(f"Answer: {response1}")

        # Test with a low-level question
        print("\n--- Test 2: Low-level question ---")
        question2 = "What is the exact fix for a DB connection limit?"
        print(f"Query: {question2}")
        response2 = query_engine.query(question2)
        print(f"Answer: {response2}")

        print("\n--- Test 3: Interactive Mode ---")
        while True:
            query = input("\nYour query: ")
            if query.lower() == 'quit':
                break
            response = query_engine.query(query)
            print(f"Answer: {response}")