import os
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from src.tools.code_analyzer import CodeAnalyzer
from src.utils.llm import get_llm

class CodeAnalysisAgent:
    def __init__(self):
        codebase_path = os.getenv("CODEBASE_PATH", "./sample_delphi_code")
        self.analyzer = CodeAnalyzer(codebase_path)
        self.llm = get_llm()

    def run(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cursor-like behavior: Fast semantic search over indexed code and context-aware analysis.
        """
        subject = ticket_data.get('subject', '')
        comments = ticket_data.get('comments', [])
        description = comments[0].get('body', '') if comments else ""
        
        query = f"{subject} {description}"
        
        # 1. Fast Semantic Search (<200ms target)
        # The codebase is assumed to be pre-indexed
        snippets = self.analyzer.search_code(query, k=5)
        
        if not snippets:
            return {
                "status": "analyzed",
                "root_cause": "No relevant code found in the indexed codebase.",
                "confidence": 0.1
            }

        # 2. Context-Aware Analysis
        code_context = ""
        for i, doc in enumerate(snippets):
            content = doc.page_content.replace("{", "{{").replace("}", "}}")
            code_context += f"\n---\n[File: {doc.metadata.get('filename')}]\n{content}\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um Analista de Código Delphi Sênior (estilo Cursor).
            Seu objetivo é realizar uma análise semântica profunda em trechos de código relacionados a um ticket de suporte.
            
            Retorne uma resposta JSON com:
            - status: "analyzed"
            - root_cause: Explicação técnica detalhada da causa raiz
            - affected_files: Lista de arquivos envolvidos
            - suggested_fix: Solução técnica (código ou lógica)
            - confidence: pontuação de 0 a 1
            """),
            ("human", f"""Contexto do Ticket:
            Assunto: {subject.replace('{', '{{').replace('}', '}}')}
            Descrição: {description.replace('{', '{{').replace('}', '}}')}

            Trechos de Código Relevantes:
            {code_context}

            Forneça uma análise estruturada.""")
        ])

        chain = prompt | self.llm
        
        try:
            response = chain.invoke({})
            content = response.content
            
            # Extract JSON from markdown if necessary
            import json
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            return analysis
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "confidence": 0
            }
