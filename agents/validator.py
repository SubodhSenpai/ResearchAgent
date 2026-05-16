from agents.base_agent import BaseAgent
from langchain_core.output_parsers import JsonOutputParser
import logging
import json
import re

logger = logging.getLogger(__name__)

VALIDATOR_PROMPT = """You are a senior Evidence Auditor. Your role is to evaluate if the research gathered so far is complete and consistent.

EVALUATION CRITERIA:
1. COMPLETENESS: Does the evidence fully answer every part of the original query?
2. CONSISTENCY: Are there contradictions between different sources?
3. RELIABILITY: Is the evidence specific facts, or just vague summaries?

Output a JSON object with these EXACT keys:
- "completeness_score": (int 0-100)
- "missing_information": (list of strings) Specific facts or data points still missing.
- "contradictions": (list of objects) Each with "topic", "source_a_claim", "source_b_claim".
- "action_recommendation": "FINALIZE" (if data is sufficient) or "TARGETED_SEARCH" (if gaps are critical).
- "reasoning": (string) Brief explanation.

Output ONLY valid JSON."""

class ValidatorAgent(BaseAgent):
    def __init__(self):
        super().__init__('Validator', VALIDATOR_PROMPT)
        self.parser = JsonOutputParser()

    def run(self, state: dict) -> dict:
        # Check if research has even started
        search_results = state.get('search_results', [])
        rag_docs = state.get('documents', [])
        query = state.get('query', '')
        
        # Load Evidence Graph for contradiction check (Sprint 3)
        from tools.evidence_graph import EvidenceGraph
        from pathlib import Path
        from config.settings import settings
        
        workspace_path = Path(settings.pageindex_workspace) / state.get('user_id', 'default')
        graph = EvidenceGraph(str(workspace_path))
        contradictions = graph.find_contradictions()

        if not search_results and not rag_docs:
            self._log("No evidence found yet.")
            return {**state, 'validator_recommendation': 'TARGETED_SEARCH', 'completeness_score': 0}

        session_id = state.get('session_id', 'unknown')
        self.trace(session_id, "input", {"query": query, "evidence_count": len(search_results) + len(rag_docs)})
        
        self._log('Auditing evidence with heuristic confidence factors')
        
        # Combine evidence for the LLM auditor
        evidence_context = "\n".join([f"- [WEB] {r.get('content', '')[:500]}" for r in search_results[:5]])
        evidence_context += "\n" + "\n".join([f"- [DOC] {str(d)[:500]}" for d in rag_docs[:5]])

        audit_prompt = f"""Evaluate the research evidence for the query: "{query}"
        
        CONFIDENCE FACTORS:
        1. CONSENSUS: Do multiple sources agree?
        2. SPECIFICITY: Are there hard facts/data or just vague statements?
        3. SOURCE QUALITY: Do the sources seem authoritative?
        4. CONTRADICTIONS: Known conflicts: {contradictions}
        
        Output a JSON object:
        - "confidence_level": "High" | "Moderate" | "Low"
        - "confidence_factors": {{{{ "consensus": 0-10, "specificity": 0-10, "authority": 0-10 }}}}
        - "missing_gaps": ["gap1", "gap2"]
        - "contradiction_alerts": ["alert1"]
        - "provenance_notes": "Summary of evidence lineage"
        - "action": "FINALIZE" | "TARGETED_SEARCH"
        """
        self.trace(session_id, "prompt", {"content": "Validator Audit Prompt"})

        try:
            chain = self._build_chain(audit_prompt)
            response = chain.invoke({"query": query, "evidence": evidence_context})
            
            # Robust JSON extraction
            import json, re
            match = re.search(r'\{.*\}', response.content, re.DOTALL)
            result = json.loads(match.group()) if match else {}
            
            self.trace(session_id, "llm_response", {"parsed": result})
            
            # Map qualitative score back to numeric for internal tracking (0, 50, 90)
            score_map = {"High": 90, "Moderate": 60, "Low": 30}
            score = score_map.get(result.get('confidence_level'), 50)

            return {
                **state,
                'completeness_score': score,
                'confidence_level': result.get('confidence_level', 'Moderate'),
                'evidence_gaps': result.get('missing_gaps', []),
                'contradictions': result.get('contradiction_alerts', []),
                'validator_recommendation': result.get('action', 'FINALIZE'),
                'provenance_summary': result.get('provenance_notes', ''),
                'messages': state['messages'] + [f"Validator: Audit complete. Confidence: {result.get('confidence_level')}"]
            }
        except Exception as e:
            self.trace(session_id, "error", {"detail": str(e)})
            logger.error(f"Validator failed: {e}")
            return {**state, 'validator_recommendation': 'FINALIZE', 'completeness_score': 50}

        except Exception as e:
            logger.error(f"Validator error: {e}")
            return {
                **state,
                'validator_recommendation': 'FINALIZE',
                'messages': state['messages'] + ["Validator: Audit failed or JSON malformed, proceeding to synthesis."]
            }
