import os
import re
import json
from typing import List, Dict, Any, Set
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

class CodeGraph:
    """Represents the dependency graph and structural metadata of the codebase."""
    def __init__(self):
        self.units: Dict[str, Dict[str, Any]] = {} # unit_name -> {path, uses: [], classes: []}
        self.methods: Dict[str, Dict[str, Any]] = {} # method_full_name -> {unit, code_snippet, calls: []}

    def add_unit(self, name: str, path: str, uses: List[str], content: str):
        # Extract classes and methods simple regex (production would use a real parser)
        classes = re.findall(r"(\w+)\s*=\s*class", content, re.IGNORECASE)
        self.units[name.lower()] = {
            "path": path,
            "uses": [u.strip().lower() for u in uses],
            "classes": classes
        }

    def add_method(self, unit_name: str, method_name: str, content: str):
        full_name = f"{unit_name}.{method_name}".lower()
        # Simple call detection (looking for method-like patterns)
        calls = re.findall(r"\.(\w+)\s*\(", content)
        self.methods[full_name] = {
            "unit": unit_name.lower(),
            "content": content,
            "calls": list(set(calls))
        }

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
        self.graph = CodeGraph()

    def index_codebase(self):
        """Walk through the codebase, index structurally and semantically."""
        documents = []
        print(f"Iniciando indexação (Estrutural + Semântica) em: {self.codebase_path}")
        
        for root, _, files in os.walk(self.codebase_path):
            for file in files:
                if file.lower().endswith(('.pas', '.dpr')):
                    file_path = os.path.join(root, file)
                    unit_name = os.path.splitext(file)[0]
                    
                    try:
                        content = self._read_file(file_path)
                        if not content: continue

                        # 1. Structural Extraction (Uses, Methods)
                        uses_match = re.search(r"uses\s+(.*?);", content, re.DOTALL | re.IGNORECASE)
                        uses = []
                        if uses_match:
                            uses = [u.strip() for u in uses_match.group(1).split(',')]
                        
                        self.graph.add_unit(unit_name, file_path, uses, content)

                        # 2. Method Extraction for Graph
                        # This is a simplified regex-based extraction
                        method_bodies = re.finditer(
                            r"(?:procedure|function|constructor|destructor)\s+([\w\.]+).*?begin(.*?)end;", 
                            content, re.DOTALL | re.IGNORECASE
                        )
                        for mb in method_bodies:
                            m_name = mb.group(1)
                            m_content = mb.group(0)
                            self.graph.add_method(unit_name, m_name, m_content)

                        # 3. Semantic Indexing (Chunks)
                        header = f"// Unit: {unit_name}\n// Path: {file_path}\n"
                        docs = self.splitter.create_documents(
                            [header + content], 
                            metadatas=[{"source": file_path, "filename": file, "unit": unit_name.lower()}]
                        )
                        documents.extend(docs)
                    except Exception as e:
                        print(f"Error indexing {file_path}: {e}")
        
        if documents:
            self.db.delete_collection()
            self.db = Chroma(
                collection_name="codebase",
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            self.db.add_documents(documents)
            print(f"Indexação concluída: {len(documents)} trechos e {len(self.graph.units)} unidades.")

    def _read_file(self, path: str) -> str:
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return ""

    def search_intelligent(self, query: str, k: int = 5) -> List[Document]:
        """Multi-layer retrieval: Semantic + Graph Expansion."""
        # Layer 1: Semantic Search
        base_results = self.db.max_marginal_relevance_search(query, k=k, fetch_k=20)
        
        # Layer 2: Graph Expansion
        expanded_docs = list(base_results)
        seen_units = {doc.metadata.get('unit') for doc in base_results if doc.metadata.get('unit')}
        
        for unit in list(seen_units):
            if unit in self.graph.units:
                # Add "uses" units as context (top 3)
                for dep in self.graph.units[unit]["uses"][:3]:
                    if dep not in seen_units and dep in self.graph.units:
                        # Find a chunk for this dependency or create a virtual one
                        dep_path = self.graph.units[dep]["path"]
                        dep_content = f"// Dependency Context: {dep}\n// Path: {dep_path}\n"
                        dep_content += f"Unit {dep} contains classes: {', '.join(self.graph.units[dep]['classes'][:5])}"
                        
                        expanded_docs.append(Document(
                            page_content=dep_content,
                            metadata={"filename": f"{dep}.pas", "type": "dependency"}
                        ))
                        seen_units.add(dep)

        return expanded_docs
