import os
import re
import logging
from typing import List
import json

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi

from src.config import settings

logger = logging.getLogger(__name__)


# =========================
# 🔥 PARSER
# =========================
class DelphiParser:
    # Regex focada em cabeçalhos da IMPLEMENTATION (ex: TForm.Acao)
    # Captura: Tipo, Nome Qualificado (Classe.Metodo), Parâmetros e Retorno
    METHOD_HEADER = re.compile(
        r"^\s*(procedure|function|constructor|destructor)\s+([\w\.]+)\s*(?:\((.*?)\))?\s*(?::\s*([\w\.]+))?\s*;",
        re.IGNORECASE | re.MULTILINE
    )

    def parse(self, content: str):
        methods = []
        
        # 1. Foca apenas na seção implementation para evitar assinaturas da interface
        parts = re.split(r"^\s*implementation\b", content, flags=re.IGNORECASE | re.MULTILINE)
        if len(parts) < 2: return []
        
        impl_content = parts[1]
        lines = impl_content.splitlines()
        
        i = 0
        n = len(lines)
        
        while i < n:
            line = lines[i].strip()
            
            header_match = self.METHOD_HEADER.match(line)
            if not header_match:
                i += 1
                continue
            
            m_type = header_match.group(1)
            m_name = header_match.group(2)
            m_params = header_match.group(3) or ""
            m_return = header_match.group(4) or ""
            
            start_index = i
            method_lines = [lines[i]]
            i += 1
            
            # 2. Busca o 'begin' inicial
            found_begin = False
            while i < n and not found_begin:
                curr_line = lines[i].lower()
                method_lines.append(lines[i])
                if "begin" in curr_line:
                    found_begin = True
                elif self.METHOD_HEADER.match(lines[i].strip()):
                    break 
                i += 1
            
            if not found_begin:
                continue

            # 3. Contador de Blocos (begin/try/case vs end)
            stack = 1
            while i < n and stack > 0:
                curr_line = lines[i]
                curr_lower = curr_line.lower()
                method_lines.append(curr_line)
                
                if re.search(r"\b(begin|try|case)\b", curr_lower):
                    stack += 1
                
                if re.search(r"\bend\s*[;.]", curr_lower):
                    stack -= 1
                
                i += 1
            
            methods.append({
                "name": m_name,
                "type": m_type,
                "params": m_params,
                "return": m_return,
                "signature": f"{m_type} {m_name}({m_params}){':' + m_return if m_return else ''}",
                "content": "\n".join(method_lines).strip()
            })
            
        return methods

# =========================
# 🔥 TOKENIZER BM25 (código)
# =========================
def tokenize_code(text: str):
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return re.findall(r'\w+', text.lower())


# =========================
# 🔥 BM25
# =========================
class HybridIndex:
    def __init__(self):
        self.docs = []
        self.bm25 = None

    def build(self, documents: List[Document]):
        self.docs = documents
        tokenized = [tokenize_code(doc.page_content) for doc in documents]
        self.bm25 = BM25Okapi(tokenized)

    def search(self, query: str, k=10):
        if not self.bm25:
            return []

        tokens = tokenize_code(query)
        scores = self.bm25.get_scores(tokens)

        ranked = sorted(
            zip(self.docs, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return [doc for doc, score in ranked[:k] if score > 0]


# =========================
# 🔥 GRAPH
# =========================
class CodeGraph:
    def __init__(self):
        self.methods = {}  # unit.method -> data
        self.call_index = {}  # call -> [methods]

    def add_method(self, unit, method, content, signature = None):
        key = f"{unit}.{method}".lower()

        calls = re.findall(r"(?:[\w]+\.)?(\w+)\s*\(", content)

        ignore = {
            'if','while','for','begin','end','try','except','finally',
            'create','free','execute','open','close','next','first'
        }

        clean_calls = []

        for c in calls:
            c = c.lower()
            if c not in ignore and len(c) > 2:
                self.call_index.setdefault(c, set()).add(key)
                clean_calls.append(c)

        self.methods[key] = {
            "unit": unit,
            "content": content,
            "calls": list(set(clean_calls)),
            "signature": signature
        }


# =========================
# 🔥 JINA WRAPPER
# =========================
class JinaEmbeddingWrapper:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def embed_documents(self, texts):
        return self.embeddings.embed_documents([f"code: {t}" for t in texts])

    def embed_query(self, text):
        return self.embeddings.embed_query(f"query: {text}")

# =========================
# 🔥 ANALYZER
# =========================
class CodeAnalyzer:

    def __init__(self, codebase_path: str = None, persist_directory: str = None):
        self.codebase_path = codebase_path or settings.CODEBASE_PATH
        self.persist_directory = persist_directory or settings.KB_CODE_DIR
        
        self.parser = DelphiParser()
        self.graph = CodeGraph()
        self.hybrid = HybridIndex()

        # Configuração Estrita: Jina Small Code -> Fallback OpenAI
        logger.info("Configurando modelos de embedding...")
        hf_token = os.getenv("HF_TOKEN")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        self.embeddings = None
        
        # 1. Tentar estritamente Jina Small Code
        try:
            model_id = settings.EMBEDDING_MODEL_JINA_NAME
            logger.info(f"Tentando carregar modelo Jina: {model_id}")
            
            hf_model = HuggingFaceEmbeddings(
                model_name=model_id,
                model_kwargs={"trust_remote_code": True, "token": hf_token},
                encode_kwargs={"normalize_embeddings": True}
            )
            self.embeddings = JinaEmbeddingWrapper(hf_model)
            logger.info("Sucesso: Modelo Jina Small Code carregado.")
        except Exception as e:
            # Tenta uma segunda vez com identificador alternativo as vezes necessário no cache
            try:
                if openai_key:
                    try:
                        from langchain_openai import OpenAIEmbeddings
                        logger.info("--- [FALLBACK: USANDO OPENAI EMBEDDINGS] ---")
                        self.embeddings = OpenAIEmbeddings(
                            model=settings.EMBEDDING_MODEL_OPENAI_NAME, 
                            api_key=openai_key
                        )
                        logger.info("Sucesso: OpenAI Embeddings carregado como fallback.")
                    except Exception as e_oa:
                        logger.error(f"Erro crítico ao carregar fallback OpenAI: {e_oa}")
                else:
                    logger.error("OpenAI API Key não encontrada para fallback.")
            except:
                logger.warning(f"OpenAI indisponível no ambiente. Motivo: {str(e)[:100]}")
                
                # 2. Fallback ÚNICO para OpenAI conforme solicitado
                if openai_key:
                    try:
                        from langchain_openai import OpenAIEmbeddings
                        logger.info("--- [FALLBACK: USANDO OPENAI EMBEDDINGS] ---")
                        self.embeddings = OpenAIEmbeddings(
                            model="text-embedding-3-large", 
                            api_key=openai_key
                        )
                        logger.info("Sucesso: OpenAI Embeddings carregado como fallback.")
                    except Exception as e_oa:
                        logger.error(f"Erro crítico ao carregar fallback OpenAI: {e_oa}")
                else:
                    logger.error("OpenAI API Key não encontrada para fallback.")

        if not self.embeddings:
            raise RuntimeError("Falha crítica: Nenhum modelo (Jina ou OpenAI) pôde ser carregado.")

        self.db = Chroma(
            collection_name="codebase",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )

    def rerank_with_llm(self, query: str, docs: List[Document], top_k=10):

        from langchain_openai import ChatOpenAI
        import json

        llm = ChatOpenAI(
            model=settings.LLM_MODEL_NAME,
            temperature=settings.LLM_TEMPERATURE
        ).bind(response_format={"type": "json_object"})

        # 🔹 reduz contexto (importantíssimo)
        docs = docs[:25]

        context = []
        for i, doc in enumerate(docs):
            context.append({
                "index": i,
                "unit": doc.metadata.get("unit"),
                "method": doc.metadata.get("method"),
                "content": doc.page_content[:1500]  # evita prompt gigante
            })

        prompt = f"""
    You are a senior Delphi engineer.

    User query:
    {query}

    Your task:
    Score each code snippet from 0 to 10 based on how relevant it is to solve the query.

    Return ONLY valid JSON in this format:
    {{
      "results": [
        {{"index": 0, "score": 8}},
        {{"index": 1, "score": 3}}
      ]
    }}

    Code snippets:
    {json.dumps(context, indent=2)}
    """

        try:
            response = llm.invoke(prompt)
            data = json.loads(response.content)
            
            # Garante que pegamos a lista de scores, independente se o LLM retornou a chave correta
            scores = data.get("results", []) if isinstance(data, dict) else data
            
            if not isinstance(scores, list):
                logger.warning(f"Reranker retornou formato inesperado: {type(scores)}")
                return docs[:top_k]

            ranked = sorted(
                scores,
                key=lambda x: x.get("score", 0) if isinstance(x, dict) else 0,
                reverse=True
            )

            result = []
            for item in ranked:
                if not isinstance(item, dict): continue
                idx = item.get("index")
                if idx is not None and idx < len(docs):
                    result.append(docs[idx])

            return result[:top_k]

        except Exception as e:
            logger.warning(f"Erro no reranker: {e}")
            return docs[:top_k]
    # =========================
    # 🔥 INDEXAÇÃO
    # =========================
    def index_codebase(self, path=None):
        path = path or self.codebase_path
        documents = []

        for root, _, files in os.walk(path):
            for file in files:
                if not file.lower().endswith((".pas", ".dpr")):
                    continue

                full_path = os.path.join(root, file)
                unit = os.path.splitext(file)[0].lower()

                content = self._read_file(full_path)
                methods = self.parser.parse(content)

                for m in methods:
                    self.graph.add_method(
                            unit,
                            m["name"],
                            m["content"],
                            signature=m.get("signature"))

                    key = f"{unit}.{m['name']}".lower()
                    calls = self.graph.methods[key]["calls"]

                    doc = Document(
                        page_content=f"""
                        Signature:
                        {m.get("signature")}

                        Type: {m.get("type")}

                        Params: {m.get("params")}

                        Return: {m.get("return")}

                        Code:
                        {m["content"]}
                        """,
                        metadata={
                            "unit": unit,
                            "method": m["name"].lower(),
                            "type": m.get("type"),
                            "signature": m.get("signature"),
                            "params": m.get("params"),
                            "return": m.get("return"),
                            "calls": json.dumps(calls),
                            "source": full_path
                        }
                    )

                    documents.append(doc)

        logger.info(f"Indexando {len(documents)} métodos...")

        self.db.reset_collection()
        self.db.add_documents(documents)
        self.hybrid.build(documents)

    # =========================
    # 🔥 SEARCH
    # =========================
    def retrieve(self, query: str):

        enriched = f"""
        query: {query}

        context:
        - delphi source code
        - procedures, functions, constructors
        - business rules
        - database operations (sql, query, select, update)
        - classes starting with T
        - possible bug location

        task:
        find relevant code snippets
        """

        vec = self.db.similarity_search_with_score(enriched, k=20)
        bm = self.hybrid.search(enriched, k=20)

        scored = {}
        doc_map = {}

        # 🔹 Vetorial (score menor = melhor)
        for doc, score in vec:
            key = f"{doc.metadata.get('unit')}.{doc.metadata.get('method')}"
            doc_map[key] = doc
            scored[key] = scored.get(key, 0) + (1 / (1 + score))

        # 🔹 BM25 (score fixo)
        for doc in bm:
            key = f"{doc.metadata.get('unit')}.{doc.metadata.get('method')}"
            if key not in doc_map:
                doc_map[key] = doc
            scored[key] = scored.get(key, 0) + 1.0

        # 🔹 Ordena por score combinado
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)

        # 🔹 Reconstrói resultado final corretamente
        result = [doc_map[key] for key, _ in ranked if key in doc_map]

        # 🔥 expansão com grafo
        expanded = self.expand_with_graph(result[:20])

        # 🔥 rerank final com LLM
        reranked = self.rerank_with_llm(query, expanded, top_k=10)

        return reranked

    # =========================
    # 🔥 GRAPH EXPANSION
    # =========================
    def expand_with_graph(self, docs):

        expanded = list(docs)
        seen = set()

        for doc in docs:
            calls_meta = doc.metadata.get("calls", "")
            calls = json.loads(calls_meta) if calls_meta else []

            for call in calls:
                targets = self.graph.call_index.get(call.lower(), set())

                for name in list(targets)[:1]:
                    if name in seen:
                        continue

                    m = self.graph.methods.get(name)
                    if not m:
                        continue

                    if m["unit"] != doc.metadata.get("unit"):

                        expanded.append(Document(
                            page_content=f"""
                            Signature:
                            {m.get("signature")}

                            Type: {m.get("type")}

                            Params: {m.get("params")}

                            Return: {m.get("return")}

                            Code:
                            {m["content"]}
                            """,
                            metadata={
                                "unit": m["unit"],
                                "method": name,
                                "type": "call"
                            }
                        ))

                        seen.add(name)

        return expanded

    def _read_file(self, path):
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(path, encoding=enc) as f:
                    return f.read()
            except:
                pass
        return ""