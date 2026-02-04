"""
Multi-Agent Search Service

Orchestrates multiple specialized search agents using a Map-Reduce pattern
to provide comprehensive answers for complex queries across many documents.
"""

import os
import re
import logging
from typing import List, Dict, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

import anthropic
import google.generativeai as genai

from app.services.extraction_service import extraction_service
from app.services.search_service import search_service
from app.services.search_agents import (
    SearchAgent,
    AgentFinding,
    AgentSearchResult,
    EquipmentSpecAgent,
    RelationshipAgent,
    IOControlAgent,
    AlarmInterlockAgent,
    SequenceAgent,
)

logger = logging.getLogger(__name__)


# Domain detection keywords
DOMAIN_KEYWORDS = {
    "equipment_spec": [
        "spec", "specification", "rating", "hp", "kw", "voltage", "manufacturer",
        "model", "location", "where is", "what type", "equipment"
    ],
    "relationship": [
        "feed", "feeds", "power", "control", "upstream", "downstream",
        "connected", "drives", "driven", "what controls", "what feeds",
        "powered by", "connects to"
    ],
    "io_control": [
        "io", "i/o", "point", "signal", "plc", "input", "output",
        "analog", "digital", "ai", "ao", "di", "do", "4-20ma", "sensor"
    ],
    "alarm_interlock": [
        "alarm", "interlock", "trip", "safety", "shutdown", "permissive",
        "setpoint", "protection", "fault", "warning", "critical"
    ],
    "sequence": [
        "sequence", "operation", "start", "stop", "mode", "procedure",
        "step", "auto", "manual", "logic", "state", "transition"
    ],
}


@dataclass
class AgentContribution:
    """Summary of an agent's contribution to the answer"""
    agent_name: str
    domain: str
    summary: str
    confidence: float
    source_count: int


@dataclass
class MultiAgentResponse:
    """Response from multi-agent search"""
    query: str
    answer: str
    sources: List[Dict]
    agents_used: List[str]
    agent_contributions: List[AgentContribution]
    confidence: float
    was_multi_agent: bool = True


class MultiAgentSearchService:
    """
    Orchestrates multiple specialized search agents for comprehensive answers.

    Uses Map-Reduce pattern:
    1. MAP: Run selected agents in parallel
    2. REDUCE: Synthesize findings into unified answer
    """

    def __init__(self):
        self.agents: Dict[str, SearchAgent] = {
            "equipment_spec": EquipmentSpecAgent(),
            "relationship": RelationshipAgent(),
            "io_control": IOControlAgent(),
            "alarm_interlock": AlarmInterlockAgent(),
            "sequence": SequenceAgent(),
        }

        self.provider = os.environ.get("LLM_PROVIDER", "claude").lower()
        self._init_llm_client()

    def _init_llm_client(self):
        """Initialize LLM client for synthesis"""
        self.anthropic_client = None
        self.gemini_model = None

        if self.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        elif self.provider == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_model = genai.GenerativeModel("gemini-3-flash-preview")

    def _has_llm(self) -> bool:
        return self.anthropic_client is not None or self.gemini_model is not None

    def should_use_multi_agent(self, query: str, search_results: List = None) -> bool:
        """
        Decide whether to use multi-agent search based on query complexity.

        CONSERVATIVE: Only use multi-agent for explicitly complex queries.
        The improved search_service now handles comprehensive search across all doc types,
        so multi-agent should only be used for truly complex analytical queries.

        Use multi-agent ONLY when:
        - Explicit comprehensive keywords AND multiple equipment tags
        - 3+ distinct domains detected in query
        - 4+ equipment tags mentioned
        """
        query_lower = query.lower()

        # Check for explicit comprehensive keywords
        comprehensive_keywords = ["comprehensive", "everything about", "all information",
                                  "complete overview", "full details", "entire system"]
        has_comprehensive_keyword = any(kw in query_lower for kw in comprehensive_keywords)

        # Check equipment tag count
        equipment_tags = self._extract_equipment_tags(query)

        # Check domain count
        domains = self._detect_domains(query)

        # ONLY use multi-agent for truly complex queries:

        # 1. Explicit request for comprehensive info + multiple equipment
        if has_comprehensive_keyword and len(equipment_tags) >= 2:
            logger.info("[MULTI_AGENT] Using multi-agent: comprehensive keyword + multiple equipment")
            return True

        # 2. Query spans 3+ domains (very complex)
        if len(domains) >= 3:
            logger.info(f"[MULTI_AGENT] Using multi-agent: {len(domains)} domains detected")
            return True

        # 3. Many equipment tags (complex system query)
        if len(equipment_tags) >= 4:
            logger.info(f"[MULTI_AGENT] Using multi-agent: {len(equipment_tags)} equipment tags")
            return True

        # Default: Use single-agent (which now searches all doc types comprehensively)
        logger.info(f"[MULTI_AGENT] Using single-agent for query: {query[:50]}...")
        return False

    def _detect_domains(self, query: str) -> Set[str]:
        """Detect which domains a query touches"""
        query_lower = query.lower()
        detected = set()

        for domain, keywords in DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in query_lower:
                    detected.add(domain)
                    break

        return detected

    def _extract_equipment_tags(self, query: str) -> List[str]:
        """Extract equipment tags from query"""
        tags = extraction_service.extract_equipment_tags(query)
        return [t.tag for t in tags]

    def _select_agents(self, domains: Set[str], query: str) -> List[str]:
        """
        Select which agents to run based on detected domains.

        Always includes equipment_spec and relationship for context.
        Adds domain-specific agents based on query.
        """
        selected = set()

        # Always include these base agents for context
        selected.add("equipment_spec")
        selected.add("relationship")

        # Add detected domain agents
        selected.update(domains)

        # If no specific domains detected, use all agents
        if len(domains) == 0:
            selected = set(self.agents.keys())

        return list(selected)

    def query(
        self,
        db: Session,
        query: str,
        project_id: Optional[int] = None
    ) -> MultiAgentResponse:
        """
        Execute multi-agent search with Map-Reduce pattern.

        Args:
            db: Database session
            query: User's query
            project_id: Optional project scope

        Returns:
            MultiAgentResponse with synthesized answer
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"[MULTI_AGENT] Processing query: {query}")
        logger.info(f"{'='*60}")

        # 1. Analyze query
        domains = self._detect_domains(query)
        equipment_tags = self._extract_equipment_tags(query)
        logger.info(f"[MULTI_AGENT] Detected domains: {domains}")
        logger.info(f"[MULTI_AGENT] Equipment tags: {equipment_tags}")

        # 2. Select agents
        selected_agents = self._select_agents(domains, query)
        logger.info(f"[MULTI_AGENT] Selected agents: {selected_agents}")

        # 3. MAP phase: Run agents in parallel
        agent_results = self._map_phase(db, query, selected_agents, equipment_tags, project_id)
        logger.info(f"[MULTI_AGENT] MAP phase complete: {len(agent_results)} agent results")

        # 4. REDUCE phase: Synthesize results
        response = self._reduce_phase(query, agent_results, equipment_tags)
        logger.info(f"[MULTI_AGENT] REDUCE phase complete")

        return response

    def _map_phase(
        self,
        db: Session,
        query: str,
        selected_agents: List[str],
        equipment_tags: List[str],
        project_id: Optional[int]
    ) -> Dict[str, AgentFinding]:
        """
        MAP phase: Run selected agents in parallel.

        Args:
            db: Database session
            query: User's query
            selected_agents: List of agent names to run
            equipment_tags: Equipment tags from query
            project_id: Optional project scope

        Returns:
            Dict mapping agent name to AgentFinding
        """
        results = {}

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=min(5, len(selected_agents))) as executor:
            futures = {}
            for agent_name in selected_agents:
                agent = self.agents[agent_name]
                future = executor.submit(
                    agent.run, db, query, equipment_tags, project_id
                )
                futures[future] = agent_name

            # Collect results as they complete
            for future in as_completed(futures, timeout=30):
                agent_name = futures[future]
                try:
                    result = future.result(timeout=30)
                    results[agent_name] = result
                    logger.info(f"[MULTI_AGENT] Agent {agent_name} complete: "
                               f"{len(result.sources)} sources, confidence={result.confidence:.2f}")
                except Exception as e:
                    logger.error(f"[MULTI_AGENT] Agent {agent_name} failed: {e}")
                    results[agent_name] = AgentFinding(
                        agent_name=agent_name,
                        domain=self.agents[agent_name].domain,
                        findings=f"Agent encountered an error: {str(e)}",
                        sources=[],
                        confidence=0.0
                    )

        return results

    def _reduce_phase(
        self,
        query: str,
        agent_results: Dict[str, AgentFinding],
        equipment_tags: List[str]
    ) -> MultiAgentResponse:
        """
        REDUCE phase: Synthesize agent findings into unified answer.

        Args:
            query: Original query
            agent_results: Dict of agent findings
            equipment_tags: Equipment tags from query

        Returns:
            MultiAgentResponse with synthesized answer
        """
        # Format agent findings for synthesis
        findings_text = self._format_findings(agent_results)

        # Synthesize with LLM
        if self._has_llm():
            answer = self._synthesize_answer(query, findings_text)
        else:
            answer = self._generate_fallback_answer(agent_results)

        # Aggregate sources and contributions
        all_sources = self._aggregate_sources(agent_results)
        contributions = self._build_contributions(agent_results)

        # Calculate overall confidence
        confidence = self._calculate_overall_confidence(agent_results)

        return MultiAgentResponse(
            query=query,
            answer=answer,
            sources=all_sources,
            agents_used=list(agent_results.keys()),
            agent_contributions=contributions,
            confidence=confidence,
            was_multi_agent=True
        )

    def _format_findings(self, agent_results: Dict[str, AgentFinding]) -> str:
        """Format agent findings for LLM synthesis"""
        parts = []

        for agent_name, finding in agent_results.items():
            if finding.confidence > 0:
                parts.append(f"\n=== {finding.domain.upper()} (from {agent_name}) ===")
                parts.append(f"Confidence: {finding.confidence:.0%}")
                parts.append(f"Sources: {len(finding.sources)}")
                parts.append("")
                parts.append(finding.findings)

                # Include source references
                if finding.sources:
                    parts.append("\nSources cited:")
                    for src in finding.sources[:5]:  # Limit source list
                        parts.append(f"  - {src.document_name}, {src.page_or_location}")

        return "\n".join(parts)

    def _synthesize_answer(self, query: str, findings_text: str) -> str:
        """Use LLM to synthesize agent findings into unified answer"""
        system_prompt = """You are synthesizing findings from multiple specialized search agents
to provide a comprehensive answer about industrial/electrical equipment systems.

Your task:
1. Combine relevant information from all agent findings
2. Resolve any conflicts (prefer higher confidence sources, PDF drawings for physical details)
3. Cite ALL sources from ALL agents that contributed information
4. Structure the answer clearly with sections if appropriate
5. Be specific with technical details (voltages, wire sizes, signal types, etc.)

FORMATTING RULES (STRICT):
1. **Executive Summary:** Start with a bold (**Answer:**) 1-sentence direct answer.
2. **Sections:** Group findings into Markdown sections (e.g., ### Specifications, ### Relationships, ### Control Logic).
3. **Bullets:** Use bullet points (-) for all lists.
4. **Bolding:** **Bold** equipment tags and key values.
5. **Discrepancies:** If agents disagree, create a "### Discrepancies" section.
6. **Sources:** List key sources at the end of each section or in a dedicated References section.

Always include document and page references for traceability.
If agents found conflicting information, note the discrepancy and explain which source is more reliable."""

        user_prompt = f"""Synthesize the following agent findings to answer this question:

Question: {query}

Agent Findings:
{findings_text}

Provide a comprehensive, well-organized answer with all relevant technical details and source citations."""

        try:
            if self.provider == "gemini" and self.gemini_model:
                response = self.gemini_model.generate_content(
                    f"{system_prompt}\n\n{user_prompt}"
                )
                return response.text
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return response.content[0].text
        except Exception as e:
            logger.error(f"[MULTI_AGENT] Synthesis LLM call failed: {e}")
            return self._generate_fallback_answer({})

        return "Unable to synthesize answer - no LLM available."

    def _generate_fallback_answer(self, agent_results: Dict[str, AgentFinding]) -> str:
        """Generate answer without LLM synthesis"""
        parts = ["Multi-agent search results:\n"]

        for agent_name, finding in agent_results.items():
            if finding.confidence > 0 and finding.sources:
                parts.append(f"\n{finding.domain.upper()}:")
                parts.append(finding.findings[:500])
                if len(finding.findings) > 500:
                    parts.append("...")

        return "\n".join(parts)

    def _aggregate_sources(self, agent_results: Dict[str, AgentFinding]) -> List[Dict]:
        """Aggregate and deduplicate sources from all agents"""
        sources = []
        seen = set()

        for agent_name, finding in agent_results.items():
            for src in finding.sources:
                # Create unique key for deduplication
                key = (src.document_name, src.page_or_location, src.equipment_tag or "")

                if key not in seen:
                    seen.add(key)
                    sources.append({
                        "document_name": src.document_name,
                        "page_number": src.page_or_location,
                        "snippet": src.content[:200] if src.content else "",
                        "equipment_tag": src.equipment_tag,
                        "source_type": src.source_type,
                        "match_type": f"multi_agent_{agent_name}",
                        "relevance_score": src.relevance_score
                    })

        # Sort by relevance
        sources.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return sources[:20]  # Limit total sources

    def _build_contributions(self, agent_results: Dict[str, AgentFinding]) -> List[AgentContribution]:
        """Build summary of each agent's contribution"""
        contributions = []

        for agent_name, finding in agent_results.items():
            # Generate short summary
            summary = finding.findings[:100] + "..." if len(finding.findings) > 100 else finding.findings

            contributions.append(AgentContribution(
                agent_name=agent_name,
                domain=finding.domain,
                summary=summary,
                confidence=finding.confidence,
                source_count=len(finding.sources)
            ))

        # Sort by confidence
        contributions.sort(key=lambda x: x.confidence, reverse=True)
        return contributions

    def _calculate_overall_confidence(self, agent_results: Dict[str, AgentFinding]) -> float:
        """Calculate overall confidence from agent results"""
        if not agent_results:
            return 0.0

        # Weight by confidence and number of sources
        total_weight = 0
        weighted_sum = 0

        for finding in agent_results.values():
            weight = 1 + len(finding.sources) * 0.1
            total_weight += weight
            weighted_sum += finding.confidence * weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0


# Singleton instance
multi_agent_search_service = MultiAgentSearchService()
