"""
Base Search Agent Class

Abstract base class for specialized search agents in the multi-agent architecture.
Each agent focuses on a specific domain and has its own search strategy and system prompt.
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

import anthropic
import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class AgentSearchResult:
    """A single search result from an agent's search phase"""
    content: str
    source_type: str  # "pdf", "supplementary", "equipment_data", "graph"
    document_name: str
    page_or_location: str  # page number or cell range
    equipment_tag: Optional[str] = None
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentFinding:
    """Findings from a single agent after analysis"""
    agent_name: str
    domain: str
    findings: str  # The analyzed answer from this agent
    sources: List[AgentSearchResult]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class SearchAgent(ABC):
    """
    Abstract base class for specialized search agents.

    Each agent:
    1. Has a specific domain focus (specs, relationships, alarms, etc.)
    2. Implements domain-specific search strategies
    3. Has a specialized system prompt for analysis
    4. Returns findings with confidence scores
    """

    def __init__(self, name: str, domain: str):
        self.name = name
        self.domain = domain
        self.provider = os.environ.get("LLM_PROVIDER", "claude").lower()
        self._init_llm_client()

    def _init_llm_client(self):
        """Initialize the LLM client based on provider"""
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
        """Check if LLM client is available"""
        return self.anthropic_client is not None or self.gemini_model is not None

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return domain-specific system prompt for this agent"""
        pass

    @abstractmethod
    def search(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> List[AgentSearchResult]:
        """
        Execute domain-specific search.

        Args:
            db: Database session
            query: The user's query
            equipment_tags: Equipment tags extracted from query
            project_id: Optional project ID to scope search

        Returns:
            List of search results relevant to this agent's domain
        """
        pass

    def analyze(
        self,
        query: str,
        search_results: List[AgentSearchResult]
    ) -> AgentFinding:
        """
        Analyze search results and produce findings.

        Args:
            query: The user's original query
            search_results: Results from the search phase

        Returns:
            AgentFinding with analysis and confidence score
        """
        if not search_results:
            return AgentFinding(
                agent_name=self.name,
                domain=self.domain,
                findings="No relevant information found in my domain.",
                sources=[],
                confidence=0.0
            )

        context = self._build_context(search_results)
        system_prompt = self.get_system_prompt()

        user_prompt = f"""Based on the following context from my specialized domain, answer this question:

Question: {query}

Context:
{context}

Provide a focused answer based ONLY on the information above.
Include specific technical details and cite sources.
If the information is incomplete, say what's missing."""

        if self._has_llm():
            findings = self._call_llm(system_prompt, user_prompt)
        else:
            findings = self._generate_fallback_findings(search_results)

        confidence = self._calculate_confidence(search_results)

        return AgentFinding(
            agent_name=self.name,
            domain=self.domain,
            findings=findings,
            sources=search_results,
            confidence=confidence
        )

    def _build_context(self, results: List[AgentSearchResult]) -> str:
        """Build context string from search results"""
        parts = []
        for i, result in enumerate(results, 1):
            source_info = f"[{result.source_type.upper()}] {result.document_name}"
            if result.page_or_location:
                source_info += f", {result.page_or_location}"
            if result.equipment_tag:
                source_info += f" (Equipment: {result.equipment_tag})"

            parts.append(f"[Source {i}] {source_info}")
            parts.append(result.content)
            parts.append("")

        return "\n".join(parts)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM to analyze results"""
        try:
            if self.provider == "gemini" and self.gemini_model:
                response = self.gemini_model.generate_content(
                    f"{system_prompt}\n\n{user_prompt}"
                )
                return response.text
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=512,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return response.content[0].text
        except Exception as e:
            logger.error(f"[{self.name}] LLM call failed: {e}")
            return f"Analysis error: {str(e)}"

        return "No LLM available for analysis."

    def _generate_fallback_findings(self, results: List[AgentSearchResult]) -> str:
        """Generate findings without LLM"""
        if not results:
            return "No relevant information found."

        parts = [f"Found {len(results)} relevant result(s):"]
        for i, result in enumerate(results[:3], 1):
            parts.append(f"{i}. {result.document_name}: {result.content[:200]}...")

        return "\n".join(parts)

    def _calculate_confidence(self, results: List[AgentSearchResult]) -> float:
        """
        Calculate confidence score based on search results.

        Factors:
        - Number of results
        - Average relevance scores
        - Source type diversity
        """
        if not results:
            return 0.0

        # Base confidence from number of results
        count_factor = min(len(results) / 5.0, 1.0)  # Max out at 5 results

        # Average relevance score
        avg_relevance = sum(r.relevance_score for r in results) / len(results)

        # Source diversity bonus
        source_types = set(r.source_type for r in results)
        diversity_bonus = 0.1 * (len(source_types) - 1) if len(source_types) > 1 else 0

        confidence = (count_factor * 0.4 + avg_relevance * 0.5 + diversity_bonus)
        return min(confidence, 1.0)

    def run(
        self,
        db: Session,
        query: str,
        equipment_tags: List[str],
        project_id: Optional[int] = None
    ) -> AgentFinding:
        """
        Execute the full agent pipeline: search + analyze.

        Args:
            db: Database session
            query: User's query
            equipment_tags: Equipment tags from query
            project_id: Optional project scope

        Returns:
            AgentFinding with complete analysis
        """
        logger.info(f"[{self.name}] Starting search for: {query[:50]}...")

        # Search phase
        search_results = self.search(db, query, equipment_tags, project_id)
        logger.info(f"[{self.name}] Found {len(search_results)} results")

        # Analyze phase
        finding = self.analyze(query, search_results)
        logger.info(f"[{self.name}] Analysis complete, confidence: {finding.confidence:.2f}")

        return finding
