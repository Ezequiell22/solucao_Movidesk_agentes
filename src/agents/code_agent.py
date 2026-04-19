import os
import re
import json
from typing import Dict, Any, List, Set
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
        Iterative Delphi code analysis agent.
        Follows a multi-step reasoning loop to gather context and analyze errors.
        """
        subject = ticket_data.get('subject', '')
        comments_list = ticket_data.get('comments', [])
        full_description = "\n".join([c.get('body', '') for c in comments_list if c.get('body')])
        
        # Iteration state
        history_snippets: List[Dict[str, str]] = []
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
                # 1. Search for code based on current query
                # For llama-3.1-8b, we use fewer snippets (k=4) and smaller context to avoid TPM limits
                snippets = self.analyzer.search_code(current_query, k=4)
                
                # Add new snippets to context, avoiding exact duplicates
                new_snippets_added = 0
                for doc in snippets:
                    file_path = doc.metadata.get('source', 'unknown')
                    content = doc.page_content
                    
                    # Check if we already have this specific chunk or too much of this file
                    snippet_id = f"{file_path}:{hash(content)}"
                    if snippet_id not in retrieved_file_paths:
                        history_snippets.append({
                            "file": doc.metadata.get('filename', 'unknown'),
                            "content": content,
                            "iteration": iterations
                        })
                        retrieved_file_paths.add(snippet_id)
                        new_snippets_added += 1

                # Prepare code context for LLM
                code_context = ""
                for i, snip in enumerate(history_snippets):
                    # Escape curly braces for LangChain prompt template
                    safe_content = snip['content'].replace("{", "{{").replace("}", "}}")
                    code_context += f"\n\n--- [TRECHO {i+1} | ARQUIVO: {snip['file']} | ITERAÇÃO: {snip['iteration']}] ---\n{safe_content}\n"

                # 2. Call LLM with iterative prompt
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """Você é um agente especialista em depuração técnica Delphi (Nível Arquiteto Sênior).
 
 SUA MISSÃO: Identificar a causa raiz exata de um problema, explorando múltiplas hipóteses e sendo cético com soluções óbvias que não resolvem o sintoma real.
 
 IDIOMA: Você DEVE responder SEMPRE em PORTUGUÊS (Brasil).
 
 PROCESSO DE RACIOCÍNIO OBRIGATÓRIO (Brainstorming & Ceticismo):
 No seu campo 'reasoning', você DEVE seguir estas etapas:
 1. LEVANTAR HIPÓTESES: Liste pelo menos 3 causas possíveis para o problema (Ex: Erro de sintaxe SQL, Erro de lógica no Delphi, Problema de conexão, Filtro incorreto).
 2. TESTE DE EVIDÊNCIA: Para cada hipótese, procure evidências no código. (Ex: "A hipótese de erro de conexão é fraca porque o método Open é chamado sem erros").
 3. ADVOGADO DO DIABO: Tente refutar sua hipótese favorita. "Por que essa correção que estou pensando pode estar errada?"
 4. AUDITORIA SQL PEDANTE: 
    - Transcreva literalmente trechos de SQL.
    - Procure por typos (ex: 'nullo', 'is null' mal posicionado, parênteses sobrando ou faltando).
 
 REGRAS DE OURO:
 - Se houver um erro de sintaxe bizarro no SQL (como 'nullo'), essa é quase certamente a causa raiz. Não a ignore por ser "simples demais".
 - Verifique o método 'SearchData' com lupa se o problema for listagem.
 - Só tome uma decisão 'FINAL' quando tiver certeza absoluta de que encontrou algo que impede a execução correta.
 - Máximo de 5 iterações.
 - Retorne APENAS JSON válido com aspas duplas.

 FORMATO DE SAÍDA:
 {{
   "decision": "CONTINUE" ou "FINAL",
   "reasoning": "Seu processo de raciocínio (HIPÓTESES -> EVIDÊNCIAS -> ADVOGADO DO DIABO -> AUDITORIA)",
   "next_query": "Busca específica para confirmar ou descartar uma hipótese",
   "final_analysis": {{
     "status": "analyzed",
     "root_cause": "Explicação técnica detalhada da causa raiz em PORTUGUÊS",
     "affected_files": ["arquivo.pas"],
     "suggested_fix": "Bloco de código Delphi com a correção exata",
     "confidence": 0.0 a 1.0
   }}
 }}
 """),
                    ("human", "ITERAÇÃO ATUAL: {iteration}/{max_iterations}\n\nCONTEXTO DO TICKET:\nAssunto: {subject}\nComentários: {context}\n\nTRECHOS DE CÓDIGO JÁ RECUPERADOS:\n{code_context}\n\nAnalise o contexto e decida se precisa de mais código ou se já pode fornecer a solução final.")
                ])

                chain = prompt | self.llm
                
                # Prepare inputs by escaping braces in content but keeping keys as placeholders
                safe_subject = subject.replace('{', '{{').replace('}', '}}')
                safe_description = full_description.replace('{', '{{').replace('}', '}}')
                # Note: code_context is already escaped in the loop above
                safe_code_context = code_context

                response = chain.invoke({
                    "iteration": iterations,
                    "max_iterations": max_iterations,
                    "subject": safe_subject,
                    "context": safe_description,
                    "code_context": safe_code_context
                })
                
                content = response.content
                
                # Robust JSON extraction
                json_str = ""
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    # Try to find the first block that looks like JSON
                    blocks = content.split("```")
                    for block in blocks:
                        clean_block = block.strip()
                        if clean_block.startswith("{") and clean_block.endswith("}"):
                            json_str = clean_block
                            break
                else:
                    # Fallback: find the first { and last }
                    start = content.find("{")
                    end = content.rfind("}")
                    if start != -1 and end != -1:
                        json_str = content[start:end+1].strip()
                
                if not json_str:
                    raise ValueError(f"No JSON found in LLM response: {content[:100]}...")

                # Use strict=False to handle potential control characters
                try:
                    result = json.loads(json_str, strict=False)
                except json.JSONDecodeError:
                    # Attempt to repair common JSON issues from smaller models
                    # 1. Replace single quotes with double quotes for keys/values
                    repaired_json = re.sub(r"'(.*?)'", r'"\1"', json_str)
                    # 2. Fix unquoted keys
                    repaired_json = re.sub(r'(\w+):', r'"\1":', repaired_json)
                    # 3. Handle trailing commas
                    repaired_json = re.sub(r',\s*([\]}])', r'\1', repaired_json)

                    try:
                        result = json.loads(repaired_json, strict=False)
                    except Exception as e:
                        print(f"Failed to repair JSON: {e}\nOriginal: {json_str}")
                        raise e
                
                if result.get("decision") == "FINAL" or iterations >= max_iterations:
                    # Return the final analysis
                    final = result.get("final_analysis", {})
                    final["iterations_count"] = iterations
                    final["reasoning_path"] = result.get("reasoning", "")
                    # Ensure status is set
                    if "status" not in final:
                        final["status"] = "analyzed"
                    return final
                else:
                    # Update query for next iteration
                    current_query = result.get("next_query", current_query)
                    print(f"Iteração {iterations}: Solicitando mais contexto com a query: '{current_query}'")
                    
            except Exception as e:
                print(f"Erro na iteração {iterations}: {e}")
                # If error, try to return whatever we have or exit
                if iterations >= 1: # Even on iteration 1 error, return a structured dictionary
                    return {
                        "status": "analyzed_with_errors",
                        "root_cause": f"A análise foi interrompida por um erro técnico na iteração {iterations}: {str(e)}",
                        "confidence": 0.3,
                        "iterations_count": iterations
                    }
                raise e

        return {
            "status": "error",
            "root_cause": "Não foi possível concluir a análise após o número máximo de iterações.",
            "confidence": 0
        }
