"""Sub-agent definitions for the research system - Ultimate Workflow."""

from ..tools import (
    arxiv_search,
    think_tool,
    conduct_research,
    research_complete,
)
from ..prompts import (
    critique_prompt,
    planning_agent_prompt,
    report_writer_prompt,
    literature_review_agent_prompt,
    individual_researcher_prompt,
    results_interpretation_agent_prompt,
)


def create_sub_agents():
    """Create and return all sub-agents for the research system.
    
    Returns:
        list: List of sub-agent dictionaries
    """
    # Phase 1: Literature Review Agent
    literature_review_agent = {
        "name": "literature-review-agent",
        "description": "Conducts systematic literature reviews using marker-based extraction. Use this agent for Phase 1 (Literature Review). The agent searches arXiv using markers (```SUMMARY, ```FULL_TEXT, ```ADD_PAPER), iteratively searches until target number of papers (5-10), and saves literature review to literature_review.md. This phase is AUTONOMOUS.",
        "system_prompt": literature_review_agent_prompt,
        "tools": [arxiv_search],
    }

    # Phase 2: Planning Agent (HUMAN APPROVAL REQUIRED)
    planning_agent = {
        "name": "planning-agent",
        "description": "Creates comprehensive research plans with human approval. Use this agent for Phase 2 (Plan Formulation). This agent generates research brief, uses collaborative planning, extracts plan using ```PLAN marker, presents plan to user, and waits for approval. This is the ONLY phase requiring human approval. Saves approved plan to research_plan.md.",
        "system_prompt": planning_agent_prompt,
    }

    # Phase 3: Individual Researcher Agent
    individual_researcher_agent = {
        "name": "individual-researcher-agent",
        "description": "Conducts focused research on specific topics assigned by the orchestrator. Use this agent for Phase 3 (Research Phase) when you need to delegate research tasks. The researcher decomposes topic into sub-queries, searches arXiv iteratively, uses think_tool for reflection, compresses findings, and saves to research_findings_[topic].md. This phase is AUTONOMOUS.",
        "system_prompt": individual_researcher_prompt,
        "tools": [arxiv_search, think_tool],
    }

    # Phase 4: Results Interpretation Agent
    results_interpretation_agent = {
        "name": "results-interpretation-agent",
        "description": "Interprets and synthesizes research findings from multiple research tasks. Use this agent for Phase 4 (Results Interpretation). The agent reads all research findings files, provides comprehensive interpretation, uses marker ```INTERPRETATION to extract interpretation, and saves to research_interpretation.md. This phase is AUTONOMOUS.",
        "system_prompt": results_interpretation_agent_prompt,
    }

    # Phase 5: Report Writer Agent
    report_writer_agent = {
        "name": "report-writer-agent",
        "description": "Writes comprehensive research documents with iterative optimization. Use this agent for Phase 5 (Report Writing). The agent reads all research materials, generates initial comprehensive report, runs iterative optimization (3-5 iterations), scores each iteration, keeps best version, and saves to final_research_document.md. This phase is AUTONOMOUS.",
        "system_prompt": report_writer_prompt,
    }

    # Phase 6: Critique Agent
    critique_sub_agent = {
        "name": "critique-agent",
        "description": "Reviews research documents with multiple reviewer perspectives and structured scoring. Use this agent for Phase 6 (Report Refinement). The agent provides structured critique with scores (1-10 scale), uses three reviewer perspectives (harsh but fair, critical but fair, open-minded), identifies improvement areas, and checks if document is comprehensive enough. This phase is AUTONOMOUS.",
        "system_prompt": critique_prompt,
    }

    return [
        literature_review_agent,
        planning_agent,
        individual_researcher_agent,
        results_interpretation_agent,
        report_writer_agent,
        critique_sub_agent,
    ]
