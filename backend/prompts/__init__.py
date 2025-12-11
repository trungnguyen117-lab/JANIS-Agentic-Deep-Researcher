"""Prompts module for agent system prompts."""

from .orchestrator_prompts import orchestrator_instructions
from .critique_prompts import critique_prompt
from .literature_review_prompts import literature_review_agent_prompt
from .plan_formulation_prompts import planning_agent_prompt
from .report_writer_prompts import report_writer_prompt
from .individual_researcher_prompts import individual_researcher_prompt
from .results_interpretation_prompts import results_interpretation_agent_prompt
from .section_writer_prompts import section_writer_prompt
from .new_prompt import new_prompt
__all__ = [
    "orchestrator_instructions",
    "critique_prompt",
    "literature_review_agent_prompt",
    "planning_agent_prompt",
    "report_writer_prompt",
    "individual_researcher_prompt",
    "results_interpretation_agent_prompt",
    "section_writer_prompt",
    "new_prompt"
]
