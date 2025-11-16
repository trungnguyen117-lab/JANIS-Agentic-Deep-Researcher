"""Sub-agent definitions for the research system - Ultimate Workflow."""

from ..tools import (
    arxiv_search,
    think_tool,
    conduct_research,
    research_complete,
    validate_json,
    count_text,
)
from ..prompts import (
    critique_prompt,
    planning_agent_prompt,
    report_writer_prompt,
    literature_review_agent_prompt,
    individual_researcher_prompt,
    results_interpretation_agent_prompt,
    section_writer_prompt,
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
        "description": "Creates comprehensive research plans with human approval. Use this agent for Phase 2 (Plan Formulation). This agent generates research brief, uses collaborative planning, creates structured outline, extracts plan using ```PLAN marker, extracts outline using ```OUTLINE marker, **MUST save outline to /plan_outline.json using write_file tool**, validates JSON using validate_json tool, presents plan to user, and waits for approval. This is the ONLY phase requiring human approval. After approval, saves plan to research_plan.md.",
        "system_prompt": planning_agent_prompt,
        "tools": [validate_json],
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
        "description": "Reviews research documents or sections with multiple reviewer perspectives and structured scoring. Use this agent for Phase 5 (Section Critique) to critique individual sections, or Phase 6 (Report Refinement) to critique the full document. The agent provides structured critique with scores (1-10 scale), uses three reviewer perspectives (harsh but fair, critical but fair, open-minded), identifies improvement areas, checks if document/section is comprehensive enough, and uses count_text tool to verify section length matches estimatedDepth. This phase is AUTONOMOUS.",
        "system_prompt": critique_prompt,
        "tools": [count_text],
    }

    # Section Writer Agent (for parallel section writing)
    section_writer_agent = {
        "name": "section-writer-agent",
        "description": "Writes individual sections of the research document based on the approved outline. Use this agent for Phase 4 (Section Writing) to write sections in parallel. The agent reads the section assignment, gathers relevant research findings, writes a comprehensive section (2-3 pages by default, unless user requests different length), includes inline citations, and saves to section_[section_id].md. This phase is AUTONOMOUS.",
        "system_prompt": section_writer_prompt,
    }

    return [
        literature_review_agent,
        planning_agent,
        individual_researcher_agent,
        results_interpretation_agent,
        report_writer_agent,
        critique_sub_agent,
        section_writer_agent,
    ]
