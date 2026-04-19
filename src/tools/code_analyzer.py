import os
import re
from typing import List
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

class DelphiCodeSplitter(RecursiveCharacterTextSplitter):
    """Custom splitter for Delphi code that tries to keep procedures/functions together."""
    def __init__(self, **kwargs):
        # Delphi procedure/function patterns - using regex for better matching
        # Note: We use \r?\n to handle different line endings
        separators = [
            r"\r?\nimplementation",
            r"\r?\nprocedure\s+",
            r"\r?\nfunction\s+",
            r"\r?\nconstructor\s+",
            r"\r?\ndestructor\s+",
            r"\r?\nclass\s+function\s+",
            r"\r?\nclass\s+procedure\s+",
            r"\r?\ninitialization",
            r"\r?\nfinalization",
            r"\r?\ninterface",
            r"\r?\nunit\s+",
            r"\r?\n\s*\{\s*T[A-Z]\w+\s*\}", # Comments like { TForm1 }
            r"\r?\n\r?\n",
            r"\r?\n",
            r" ",
            r""
        ]
        super().__init__(separators=separators, is_separator_regex=True, **kwargs)

class CodeAnalyzer:
    def __init__(self, codebase_path: str, persist_directory: str = "./data/code_db"):
        self.codebase_path = codebase_path
        self.persist_directory = persist_directory
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = Chroma(
            collection_name="codebase",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        # Increased chunk size to 4000 to avoid truncating long SQL methods
        self.splitter = DelphiCodeSplitter(chunk_size=4000, chunk_overlap=800)

    def index_codebase(self):
        """Walk through the codebase and index all Delphi files (.pas, .dpr, .dfm)."""
        documents = []
        print(f"Iniciando indexação do codebase: {self.codebase_path}")
        for root, _, files in os.walk(self.codebase_path):
            for file in files:
                if file.lower().endswith(('.pas', '.dpr', '.dfm', '.inc')):
                    file_path = os.path.join(root, file)
                    try:
                        content = ""
                        for enc in ['utf-8', 'latin-1', 'cp1252']:
                            try:
                                with open(file_path, 'r', encoding=enc) as f:
                                    content = f.read()
                                break
                            except UnicodeDecodeError:
                                continue
                        
                        if not content:
                            continue

                        # Add filename and path to content to help retrieval
                        # This helps the LLM know which file it's looking at even if the metadata is lost
                        header = f"// File: {file}\n// Path: {file_path}\n"
                        content_with_header = header + content

                        docs = self.splitter.create_documents(
                            [content_with_header], 
                            metadatas=[{"source": file_path, "filename": file}]
                        )
                        documents.extend(docs)
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
        
        if documents:
            print(f"Indexando {len(documents)} trechos de código...")
            self.db.delete_collection()
            self.db = Chroma(
                collection_name="codebase",
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            self.db.add_documents(documents)
            print("Indexação concluída com sucesso.")

    def search_code(self, query: str, k: int = 10) -> List[Document]:
        """Search the codebase using MMR to ensure diversity and avoid redundant headers."""
        # Increased k to 10 and fetch_k to 30 for better coverage
        return self.db.max_marginal_relevance_search(query, k=k, fetch_k=30)
