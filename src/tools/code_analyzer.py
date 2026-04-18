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
        # Delphi procedure/function patterns
        separators = [
            "\nprocedure ",
            "\nfunction ",
            "\nconstructor ",
            "\ndestructor ",
            "\ninitialization",
            "\nfinalization",
            "\nend.",
            "\n\n",
            "\n",
            " ",
            ""
        ]
        super().__init__(separators=separators, **kwargs)

class CodeAnalyzer:
    def __init__(self, codebase_path: str, persist_directory: str = "./data/code_db"):
        self.codebase_path = codebase_path
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = Chroma(
            collection_name="codebase",
            embedding_function=self.embeddings,
            persist_directory=persist_directory
        )
        self.splitter = DelphiCodeSplitter(chunk_size=1000, chunk_overlap=200)

    def index_codebase(self):
        """Walk through the codebase and index all Delphi files (.pas, .dpr, .dfm)."""
        documents = []
        for root, _, files in os.walk(self.codebase_path):
            for file in files:
                if file.endswith(('.pas', '.dpr', '.dfm')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='latin-1') as f:
                            content = f.read()
                            docs = self.splitter.create_documents(
                                [content], 
                                metadatas=[{"source": file_path, "filename": file}]
                            )
                            documents.extend(docs)
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
        
        if documents:
            self.db.add_documents(documents)

    def search_code(self, query: str, k: int = 5) -> List[Document]:
        """Search the codebase for relevant snippets."""
        return self.db.similarity_search(query, k=k)
