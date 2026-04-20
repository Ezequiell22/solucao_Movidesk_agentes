import os
import re
import json
from typing import Dict, Any, List, Set
from langchain_core.prompts import ChatPromptTemplate
from src.tools.code_analyzer import CodeAnalyzer
from src.utils.llm import get_llm

class CodeAnalysisAgent:
    def __init__(self, analyzer: CodeAnalyzer = None):
        if analyzer:
            self.analyzer = analyzer
        else:
            codebase_path = os.getenv("CODEBASE_PATH", "./sample_delphi_code")
            self.analyzer = CodeAnalyzer(codebase_path)
        self.llm = get_llm()

    def run(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Iterative Delphi code analysis agent with Graph-Aware Retrieval.
        """
        subject = ticket_data.get('subject', '')
        comments_list = ticket_data.get('comments', [])
        full_description = "\n".join([c.get('body', '') for c in comments_list if c.get('body')])
        
        # Iteration state
        history_snippets: List[Dict[str, Any]] = []
        retrieved_file_paths: Set[str] = set()
        iterations = 0
        max_iterations = 5
        
        # Initial query based on ticket
        current_query = f"{subject} {full_description}"
        current_query = re.sub(r"\[Comentario \d+\]", "", current_query)

        while iterations < max_iterations:
            iterations += 1
            print(f"\n--- [AGENTE 2: ITERAÇÃO {iterations}/{max_iterations}] ---")
            
            try:
                # 1. Multi-Layer Retrieval (Semantic + Graph Expansion)
                snippets = self.analyzer.search_intelligent(current_query, k=4)
                
                # Add new snippets to context
                for doc in snippets:
                    file_path = doc.metadata.get('source', 'unknown')
                    content = doc.page_content
                    snippet_id = f"{file_path}:{hash(content)}"
                    if snippet_id not in retrieved_file_paths:
                        history_snippets.append({
                            "file": doc.metadata.get('filename', 'unknown'),
                            "content": content,
                            "iteration": iterations,
                            "type": doc.metadata.get('type', 'code')
                        })
                        retrieved_file_paths.add(snippet_id)

                # 2. Context Builder (Structured Context)
                entry_points = [s for s in history_snippets if s['type'] == 'code']
                dependencies = [s for s in history_snippets if s['type'] == 'dependency']
                
                code_context = "[LÓGICA PRINCIPAL E MÉTODOS ENCONTRADOS]\n"
                for s in entry_points:
                    safe_content = s['content'].replace("{", "{{").replace("}", "}}")
                    code_context += f"--- Arquivo: {s['file']} ---\n{safe_content}\n"
                
                if dependencies:
                    code_context += "\n[CONTEXTO DE DEPENDÊNCIAS (USES / INTERFACES)]\n"
                    for s in dependencies:
                        code_context += f"--- {s['file']} ---\n{s['content']}\n"

                # 3. Architect-Level Prompt
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """Você é um Arquiteto de Software Delphi Sênior especializado em depuração de sistemas complexos.
 
 SUA MISSÃO: Realizar uma análise profunda e multi-camadas para encontrar a causa raiz exata.
 
 [ESTRATÉGIA DE ANÁLISE]
 1. MAPEAMENTO: Use o [CONTEXTO DE DEPENDÊNCIAS] para entender como as Units se relacionam.
 2. RASTREAMENTO: Siga o fluxo do ticket desde a View até o DAO/Banco de Dados.
 3. AUDITORIA CIRÚRGICA: 
    - Transcreva literalmente qualquer SQL encontrado.
    - Verifique cada caractere: vírgulas, parênteses, aspas, palavras-chave (nullo, is null, etc).
 4. VERIFICAÇÃO DE FLUXO: "Se eu corrigir X, o sintoma Y do ticket realmente desaparece?"
 
 REGRAS:
 - Seja cético. Se o código parece certo mas o erro persiste, peça para ver o corpo de funções chamadas (especifique o nome).
 - Máximo de 5 iterações. Se não tiver certeza, use 'CONTINUE' e peça exatamente o que falta.
 - Responda SEMPRE em PORTUGUÊS.
 - Você DEVE retornar um JSON válido seguindo estritamente o esquema solicitado.

 FORMATO DE SAÍDA (JSON):
 {{
   "decision": "CONTINUE" ou "FINAL",
   "reasoning": "Seu raciocínio técnico detalhado (MAPEAMENTO -> RASTREAMENTO -> AUDITORIA -> VALIDAÇÃO)",
   "next_query": "Busca específica baseada no grafo de chamadas ou unit do 'uses'",
   "final_analysis": {{
     "status": "analyzed",
     "root_cause": "Causa raiz técnica detalhada",
     "affected_files": ["unit.pas"],
     "suggested_fix": "Código Delphi exato para a correção",
     "confidence": 0.0 a 1.0
   }}
 }}
 """),
                    ("human", "ITERAÇÃO: {iteration}/{max_iterations}\n\nCONTEXTO DO TICKET:\nAssunto: {subject}\nComentários: {context}\n\nCÓDIGO ESTRUTURADO:\n{code_context}\n\nAnalise as camadas e decida o próximo passo.")
                ])

                # Use response_format for guaranteed JSON structure
                if hasattr(self.llm, "bind"):
                    chain = prompt | self.llm.bind(response_format={"type": "json_object"})
                else:
                    chain = prompt | self.llm
                
                safe_subject = subject.replace('{', '{{').replace('}', '}}')
                safe_description = full_description.replace('{', '{{').replace('}', '}}')

                response = chain.invoke({
                    "iteration": iterations,
                    "max_iterations": max_iterations,
                    "subject": safe_subject,
                    "context": safe_description,
                    "code_context": code_context
                })
                
                content = response.content
                
                # Directly load JSON since response_format is set to json_object
                try:
                    result = json.loads(content, strict=False)
                except json.JSONDecodeError:
                    # Fallback to robust extraction only if json_object fails
                    json_str = ""
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                    else:
                        start = content.find("{")
                        end = content.rfind("}")
                        if start != -1 and end != -1:
                            json_str = content[start:end+1].strip()
                    
                    if not json_str:
                        raise ValueError(f"No JSON found in LLM response")
                    
                    result = json.loads(json_str, strict=False)
                
                if result.get("decision") == "FINAL" or iterations >= max_iterations:
                    final = result.get("final_analysis", {})
                    final["iterations_count"] = iterations
                    final["reasoning_path"] = result.get("reasoning", "")
                    if "status" not in final:
                        final["status"] = "analyzed"
                    return final
                else:
                    current_query = result.get("next_query", current_query)
                    print(f"Iteração {iterations}: Próxima busca: '{current_query}'")
                    
            except Exception as e:
                print(f"Erro na iteração {iterations}: {e}")
                if iterations >= 1:
                    return {
                        "status": "analyzed_with_errors",
                        "root_cause": f"Erro técnico na iteração {iterations}: {str(e)}",
                        "confidence": 0.3,
                        "iterations_count": iterations
                    }
                raise e

        return {
            "status": "error",
            "root_cause": "Limite de iterações atingido.",
            "confidence": 0
        }
