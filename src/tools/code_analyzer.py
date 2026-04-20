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
        self.inheritance: Dict[str, str] = {} # class -> base_class

    def add_unit(self, name: str, path: str, uses: List[str], content: str):
        # Improved regex for class extraction including inheritance
        # e.g., TForm1 = class(TForm)
        class_defs = re.findall(r"(\w+)\s*=\s*class\s*(?:\(([\w\.]+)\))?", content, re.IGNORECASE)
        classes = []
        for c_name, base_c in class_defs:
            classes.append(c_name)
            if base_c:
                self.inheritance[c_name.lower()] = base_c.lower()

        self.units[name.lower()] = {
            "path": path,
            "uses": [u.strip().lower() for u in uses],
            "classes": classes
        }

    def add_method(self, unit_name: str, method_name: str, content: str):
        full_name = f"{unit_name}.{method_name}".lower()
        # Deep Call Detection: look for method calls (object.method, self.method, method(args))
        # This is a heuristic to build the call graph
        calls = re.findall(r"(?:[\w\.]+\.)?(\w+)\s*\(", content)
        
        # Filter common keywords to avoid noise in the graph
        common_keywords = {'if', 'while', 'for', 'begin', 'end', 'try', 'except', 'finally', 'case', 'repeat', 'until', 'procedure', 'function', 'constructor', 'destructor'}
        clean_calls = [c for c in calls if c.lower() not in common_keywords]

        self.methods[full_name] = {
            "unit": unit_name.lower(),
            "content": content,
            "calls": list(set(clean_calls))
        }

class CodeAnalyzer:
    def __init__(self, codebase_path: str, persist_directory: str = "./data/code_db"):
        self.codebase_path = codebase_path
        self.persist_directory = persist_directory
        
        # Substituímos o Jina-Base pelo Jina-Small-Code para evitar travamentos e consumo excessivo de RAM.
        # O modelo 'small' é extremamente eficiente, carrega rápido e mantém a especialização em código.
        # Além disso, removemos o 'trust_remote_code' que costuma causar hangs em downloads de arquivos Python externos.
        print("--- [PREPARANDO MODELO DE EMBEDDING] ---")
        print("Modelo: jinaai/jina-embeddings-v2-small-code (Especializado em Código)")
        
        try:
            # O identificador correto no HuggingFace é "jinaai/jina-embeddings-v2-small-code"
            # Adicionamos 'trust_remote_code=True' pois o Jina usa uma arquitetura customizada de Bert.
            self.embeddings = HuggingFaceEmbeddings(
                model_name="jinaai/jina-embeddings-v2-small-code",
                model_kwargs={'trust_remote_code': True}
            )
            print("Sucesso: Modelo de embedding carregado.")
        except Exception as e:
            print(f"Aviso: Erro ao carregar Jina ({e}). Usando fallback estável 'all-MiniLM-L6-v2'.")
            # Fallback para o modelo que sabemos que funciona e é padrão
            self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

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
        print(f"--- [INDEXAÇÃO ESTRUTURAL + SEMÂNTICA] ---")
        print(f"Diretório: {self.codebase_path}")
        
        files_to_index = []
        for root, _, files in os.walk(self.codebase_path):
            for file in files:
                if file.lower().endswith(('.pas', '.dpr')):
                    files_to_index.append(os.path.join(root, file))
        
        total_files = len(files_to_index)
        print(f"Arquivos encontrados: {total_files}")

        for i, file_path in enumerate(files_to_index):
            unit_name = os.path.splitext(os.path.basename(file_path))[0]
            if i % 10 == 0 or i == total_files - 1:
                print(f"Processando [{i+1}/{total_files}]: {unit_name}")
            
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
                    metadatas=[{"source": file_path, "filename": os.path.basename(file_path), "unit": unit_name.lower()}]
                )
                documents.extend(docs)
            except Exception as e:
                print(f"Erro ao indexar {file_path}: {e}")
        
        if documents:
            print(f"Indexando {len(documents)} trechos no banco vetorial...")
            self.db.delete_collection()
            self.db = Chroma(
                collection_name="codebase",
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            self.db.add_documents(documents)
            print(f"--- [INDEXAÇÃO CONCLUÍDA: {len(documents)} trechos | {len(self.graph.units)} unidades] ---")

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
        seen_methods = set()
        
        # Expansion by Unit Dependencies (uses)
        for unit in list(seen_units):
            if unit in self.graph.units:
                for dep in self.graph.units[unit]["uses"][:3]:
                    if dep not in seen_units and dep in self.graph.units:
                        dep_path = self.graph.units[dep]["path"]
                        dep_content = f"// Dependency Context: {dep}\n// Path: {dep_path}\n"
                        dep_content += f"Unit {dep} contains classes: {', '.join(self.graph.units[dep]['classes'][:5])}"
                        
                        expanded_docs.append(Document(
                            page_content=dep_content,
                            metadata={"filename": f"{dep}.pas", "type": "dependency", "unit": dep}
                        ))
                        seen_units.add(dep)

        # Expansion by Call Graph (methods called in snippets)
        for doc in base_results:
            content = doc.page_content
            # Try to identify which method this snippet belongs to
            for m_full_name, m_info in self.graph.methods.items():
                if m_info["unit"] == doc.metadata.get("unit") and m_full_name in content.lower():
                    # If we found the method, add context about what it calls
                    for call in m_info["calls"][:5]:
                        # Search if we have the implementation of the called method
                        for target_m_name, target_m_info in self.graph.methods.items():
                            if target_m_name.endswith(f".{call.lower()}"):
                                if target_m_name not in seen_methods:
                                    expanded_docs.append(Document(
                                        page_content=f"// Call Graph Context: {target_m_name}\n{target_m_info['content']}",
                                        metadata={"filename": f"{target_m_info['unit']}.pas", "type": "call", "method": target_m_name}
                                    ))
                                    seen_methods.add(target_m_name)
        
        return expanded_docs
