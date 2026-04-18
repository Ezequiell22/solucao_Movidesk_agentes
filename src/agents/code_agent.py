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
        # Extracting subject and all comments for full context
        subject = ticket_data.get('subject', '')
        comments_list = ticket_data.get('comments', [])
        
        # Combine all comment bodies into a single description for better context
        full_description = "\n".join([c.get('body', '') for c in comments_list if c.get('body')])
        
        query = f"{subject} {full_description}"
        
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
            - root_cause: Explicação técnica detalhada da causa raiz.
            - affected_files: Lista de arquivos envolvidos.
            - suggested_fix: Sugestão técnica de correção. Esta seção DEVE conter trechos de código mínimos e principais (diffs ou blocos de código) necessários para resolver o problema, focando em uma implementação prática.
            - confidence: pontuação de 0 a 1
            """),
            ("human", "Contexto do Ticket:\nAssunto: {subject}\nContexto (Comentários): {context}\n\nTrechos de Código Relevantes:\n{code_context}\n\nForneça uma análise estruturada, garantindo que a sugestão de correção inclua os trechos de código Delphi necessários baseando-se em todo o contexto fornecido pelos comentários.")
        ])

        chain = prompt | self.llm
        
        try:
            # Prepare inputs by escaping braces in content but keeping keys as placeholders
            safe_subject = subject.replace('{', '{{').replace('}', '}}')
            safe_description = full_description.replace('{', '{{').replace('}', '}}')
            safe_code_context = code_context.replace('{', '{{').replace('}', '}}')

            response = chain.invoke({
                "subject": safe_subject,
                "context": safe_description,
                "code_context": safe_code_context
            })
            content = response.content
            
            # Extract JSON from markdown if necessary for structured logic
            import json
            analysis = {"status": "analyzed", "full_analysis": content} # Always include raw content
            
            try:
                json_str = content
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                
                # Use strict=False to handle potential control characters (newlines in code)
                parsed_json = json.loads(json_str, strict=False)
                analysis.update(parsed_json)
            except Exception as e:
                print(f"Aviso: Erro ao parsear JSON estruturado (Agente 2), mas mantendo conteúdo bruto: {e}")
            
            return analysis
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "full_analysis": f"Erro técnico na análise: {str(e)}",
                "confidence": 0
            }
