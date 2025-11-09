"""Section-specific writing tips inspired by AgentLaboratory and AI Scientist paper.

These tips provide guidance for writing different sections of research reports.
Modified from AgentLaboratory's per_section_tips and AI Scientist paper.
"""

# Section writing guidelines for research reports
SECTION_WRITING_TIPS = {
    "abstract": """
- TL;DR of the report
- What are we trying to do and why is it relevant?
- Why is this hard or important?
- How do we approach it (i.e. our contribution/approach!)
- What did we find (e.g. Key findings and insights)
- This should be a single, well-flowing paragraph

Please make sure the abstract reads smoothly and is well-motivated. This should be one continuous paragraph with no breaks.
""",
    
    "introduction": """
- Longer version of the Abstract, providing context for the entire report
- What are we trying to do and why is it relevant?
- Why is this hard or important?
- How do we approach it (i.e. our contribution/approach!)
- What did we find (e.g. Key findings and insights)
- Specifically list your main contributions or findings as bullet points
- If space allows, mention future directions or implications
""",
    
    "related_work": """
- Academic siblings of our work, i.e. alternative attempts in literature at trying to solve the same problem
- Goal is to "Compare and contrast" - how does their approach differ in either assumptions or method?
- If their method is applicable to our problem setting, we should compare it
- If not applicable, there needs to be a clear statement why a given method is not applicable
- Note: Just describing what another paper is doing is not enough. We need to compare and contrast.
""",
    
    "background": """
- Academic ancestors of our work, i.e. all concepts and prior work that are required for understanding our approach
- Usually includes foundational concepts and terminology
- Formally introduces the problem setting and notation when necessary
- Highlights any specific assumptions that are made that are unusual
- Make sure to use clear explanations and definitions
- Note: If our report introduces a novel problem setting, it's best to have a separate section
""",
    
    "methods": """
- What we do. Why we do it.
- All described using clear methodology and approach
- Make sure you clearly report the methodology and approach used
- Explain the research process and information gathering methods
- Describe how sources were selected and analyzed
""",
    
    "analysis": """
- Shows the analysis of the research findings
- Includes key insights and interpretations
- Compares different perspectives or approaches when relevant
- Includes quantitative or qualitative findings as appropriate
- Discusses patterns, trends, and relationships identified
- Discusses limitations of the analysis or findings
- Make sure to include all relevant findings and insights
""",
    
    "discussion": """
- Brief recap of the entire report
- Synthesizes key findings and insights
- Discusses implications and significance
- Addresses limitations and future directions
- Provides conclusions and recommendations
""",
    
    "conclusion": """
- Summarizes the main findings and contributions
- Highlights the most important insights
- Discusses broader implications
- Suggests future research directions or applications
- Provides a strong closing statement
""",
}

def get_section_tips(section_name: str) -> str:
    """Get writing tips for a specific section.
    
    Args:
        section_name: Name of the section (e.g., "abstract", "introduction")
    
    Returns:
        Writing tips for the section, or empty string if section not found
    """
    return SECTION_WRITING_TIPS.get(section_name.lower(), "")

def get_all_section_tips() -> dict:
    """Get all section writing tips.
    
    Returns:
        Dictionary of all section tips
    """
    return SECTION_WRITING_TIPS.copy()

