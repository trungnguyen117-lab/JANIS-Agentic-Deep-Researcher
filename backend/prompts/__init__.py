"""Prompts module for agent system prompts."""

from .research_prompts import research_instructions
from .orchestrator_prompts import orchestrator_instructions
from .critique_prompts import critique_prompt, research_prompt
from .literature_review_prompts import (
    literature_review_agent_prompt,
)
from .research_agent_prompts import research_agent_prompt
from .plan_formulation_prompts import (
    planning_agent_prompt,
    plan_formulation_prompt,
    plan_refinement_prompt,
)
from .report_writer_prompts import report_writer_prompt
from .research_supervisor_prompts import research_supervisor_prompt
from .individual_researcher_prompts import individual_researcher_prompt
from .results_interpretation_prompts import results_interpretation_agent_prompt
from .section_writer_prompts import section_writer_prompt
from .section_writing_tips import (
    SECTION_WRITING_TIPS,
    get_section_tips,
    get_all_section_tips,
)

__all__ = [
    "research_instructions",
    "orchestrator_instructions",
    "critique_prompt",
    "research_prompt",
    "research_agent_prompt",
    "planning_agent_prompt",
    "plan_formulation_prompt",
    "plan_refinement_prompt",
    "report_writer_prompt",
    "literature_review_agent_prompt",
    "research_supervisor_prompt",
    "individual_researcher_prompt",
    "results_interpretation_agent_prompt",
    "section_writer_prompt",
    "SECTION_WRITING_TIPS",
    "get_section_tips",
    "get_all_section_tips",
]

