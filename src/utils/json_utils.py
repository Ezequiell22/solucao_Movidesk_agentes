import json
import re
import logging

logger = logging.getLogger(__name__)

def extract_json_from_text(text: str) -> str:
    """
    Extracts the first JSON-like structure from a text string.
    Handles markdown blocks and loose text.
    """
    text = text.strip()
    
    # 1. Try markdown blocks
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        blocks = text.split("```")
        for block in blocks:
            clean_block = block.strip()
            if clean_block.startswith("{") and clean_block.endswith("}"):
                return clean_block
    
    # 2. Fallback: Find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start:end+1].strip()
    
    return ""

def repair_json_string(json_str: str) -> str:
    """
    Attempts to repair common JSON issues like single quotes or unquoted keys.
    """
    # Replace single quotes with double quotes for keys/values
    # (Careful with apostrophes inside strings, but for basic JSON it works)
    repaired = re.sub(r"'(.*?)'", r'"\1"', json_str)
    
    # Fix unquoted keys (e.g., {decision: "FINAL"} -> {"decision": "FINAL"})
    repaired = re.sub(r'(\w+):', r'"\1":', repaired)
    
    # Handle trailing commas
    repaired = re.sub(r',\s*([\]}])', r'\1', repaired)
    
    return repaired

def parse_llm_json(content: str) -> dict:
    """
    Unified utility to parse JSON from LLM responses with robust extraction and repair.
    """
    json_str = extract_json_from_text(content)
    
    if not json_str:
        logger.error(f"Failed to find JSON in content: {content[:200]}...")
        raise ValueError("No valid JSON structure found in LLM response.")

    try:
        return json.loads(json_str, strict=False)
    except json.JSONDecodeError as e:
        logger.warning(f"Initial JSON parse failed, attempting repair: {e}")
        repaired = repair_json_string(json_str)
        try:
            return json.loads(repaired, strict=False)
        except Exception as final_err:
            logger.error(f"JSON repair failed: {final_err}")
            raise ValueError(f"Failed to parse LLM JSON even after repair: {final_err}")
