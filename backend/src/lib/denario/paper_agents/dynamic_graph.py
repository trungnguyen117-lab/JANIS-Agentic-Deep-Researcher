"""Dynamic graph builder that creates paper sections based on outline structure."""

from langgraph.graph import START, StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .parameters import GraphState
from .paper_node import abstract_node, citations_node, keywords_node, plots_node, refine_results
from .reader import preprocess_node
from .routers import citation_router


def create_section_node(section_id: str, section_title: str, section_description: str, subsections: list = None):
    """
    Create a section node function for a specific section from the outline.
    
    Args:
        section_id: Unique identifier for the section (e.g., "intro", "related_work")
        section_title: Title of the section (e.g., "Introduction", "Related Work")
        section_description: Description of what should be covered in this section
        subsections: Optional list of subsections with id, title, description, order
    
    Returns:
        A node function that can be added to the graph
    """
    from langchain_core.runnables import RunnableConfig
    from .paper_node import section_node
    
    # Create a prompt function that includes outline guidance
    def section_prompt(state: GraphState):
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Build subsection guidance if available
        subsection_guidance = ""
        if subsections:
            subsection_guidance = "\n\n**IMPORTANT - Include these subsections:**\n"
            # Filter out non-dict items and sort by order
            valid_subsections = [s for s in subsections if isinstance(s, dict)]
            sorted_subsections = sorted(valid_subsections, key=lambda x: x.get('order', 0) if isinstance(x, dict) else 0)
            for subsec in sorted_subsections:
                if isinstance(subsec, dict):
                    title = subsec.get('title', '')
                    desc = subsec.get('description', '')
                    if title and desc:
                        subsection_guidance += f"- {title}: {desc}\n"
                    elif title:
                        # If no description, just show the title
                        subsection_guidance += f"- {title}\n"
        
        # Use generic section prompt but with outline guidance
        # Get previous sections for context - safely handle if paper is dict or string
        prev_sections = []
        
        # Safely access state - handle both dict and TypedDict
        # State should always be a dict-like object (GraphState TypedDict)
        try:
            if hasattr(state, 'get'):
                paper_dict = state.get('paper', {})
                writer = state.get('writer', 'scientist')
            elif isinstance(state, dict):
                paper_dict = state.get('paper', {})
                writer = state.get('writer', 'scientist')
            else:
                # Fallback if state is not dict-like
                paper_dict = {}
                writer = 'scientist'
        except (AttributeError, TypeError):
            paper_dict = {}
            writer = 'scientist'
        
        # Ensure paper_dict is a dict, not a string
        if not isinstance(paper_dict, dict):
            paper_dict = {}
        
        # Get previous sections
        intro = paper_dict.get('Introduction', '') if isinstance(paper_dict, dict) else ''
        methods = paper_dict.get('Methods', '') if isinstance(paper_dict, dict) else ''
        results = paper_dict.get('Results', '') if isinstance(paper_dict, dict) else ''
        
        if intro and isinstance(intro, str):
            prev_sections.append(f"Introduction: {intro[:500]}")
        if methods and isinstance(methods, str):
            prev_sections.append(f"Methods: {methods[:500]}")
        if results and isinstance(results, str):
            prev_sections.append(f"Results: {results[:500]}")
        
        prev_context = "\n\n".join(prev_sections) if prev_sections else "No previous sections yet."
        
        # Safely get paper fields
        paper_title = paper_dict.get('Title', '') if isinstance(paper_dict, dict) else ''
        paper_abstract = paper_dict.get('Abstract', '') if isinstance(paper_dict, dict) else ''
        
        return [
            SystemMessage(content=f"""You are a {writer}"""),
            HumanMessage(content=f"""Write the "{section_title}" section for a scientific paper in LaTeX.

**IMPORTANT - Section Requirements:**
{section_description}
{subsection_guidance}

Paper title: 
{paper_title}

Paper abstract: 
{paper_abstract}

Previous sections (for context):
{prev_context}

Please respond in this format:

\\begin{{{section_title}}}
<{section_title.upper().replace(' ', '_')}>
\\end{{{section_title}}}

In <{section_title.upper().replace(' ', '_')}>, place the {section_title} section. Please, follow these guidelines:
- Write your response in LaTeX
- **CRITICAL**: Follow the section description above and include ALL specified subsections
- Connect with previous sections when relevant
- Do not add citations (they will be added later)
- Do not create commands, e.g. \\MBH
- You can create subsections and subsubsections, but not sections
- Do not write subsections titles in capital letters
- The first letter of subsection titles should be in capital

Please make sure the section reads smoothly and is well-motivated.
""")
        ]
    
    # Create reflection function (optional, only for introduction-like sections)
    def section_reflection(state: GraphState):
        if section_id in ['intro', 'introduction']:
            # Only use reflection for introduction
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Safely get paper fields
            try:
                if hasattr(state, 'get'):
                    paper_dict = state.get('paper', {})
                    writer = state.get('writer', 'scientist')
                elif isinstance(state, dict):
                    paper_dict = state.get('paper', {})
                    writer = state.get('writer', 'scientist')
                else:
                    paper_dict = {}
                    writer = 'scientist'
            except (AttributeError, TypeError):
                paper_dict = {}
                writer = 'scientist'
            
            # Ensure paper_dict is a dict, not a string
            if not isinstance(paper_dict, dict):
                paper_dict = {}
            
            paper_title = paper_dict.get('Title', '') if isinstance(paper_dict, dict) else ''
            paper_abstract = paper_dict.get('Abstract', '') if isinstance(paper_dict, dict) else ''
            prev_section = paper_dict.get(section_title, '') if isinstance(paper_dict, dict) else ''
            
            return [
                SystemMessage(content=f"""You are a {writer}"""),
                HumanMessage(content=f"""Rewrite the {section_title} section below to make it more clear. Take into account the paper title, abstract, and other sections.

Paper title: 
{paper_title}

Paper abstract: 
{paper_abstract}

Previous {section_title}: 
{prev_section}

Section description:
{section_description}

Respond with in the following format:

\\begin{{{section_title}}}
<{section_title.upper().replace(' ', '_')}>
\\end{{{section_title}}}

In <{section_title.upper().replace(' ', '_')}>, place the new {section_title}. 

**CRITICAL**: The LaTeX block must use exactly: \\begin{{{section_title}}} ... \\end{{{section_title}}}

Follow the section description and guidelines.
""")
            ]
        return None
    
    # Return a node function that uses section_node with custom prompt
    # Note: section_node expects section_name to match what's used in LaTeX block extraction
    # We'll use section_title for the LaTeX block name (spaces are OK, extract_latex_block handles them)
    def dynamic_section_node(state: GraphState, config: RunnableConfig):
        return section_node(
            state, 
            config, 
            section_name=section_title,  # Use the actual section title for LaTeX block
            prompt_fn=section_prompt,
            reflection_fn=section_reflection if section_id in ['intro', 'introduction'] else None
        )
    
    return dynamic_section_node


def build_dynamic_graph(outline: dict, mermaid_diagram: bool = False):
    """
    Build a dynamic graph based on the outline structure.
    
    Args:
        outline: Outline dictionary with 'sections' key
        mermaid_diagram: Whether to generate a mermaid diagram
    
    Returns:
        Compiled LangGraph graph
    """
    if not outline or 'sections' not in outline:
        raise ValueError("Outline must have 'sections' key")
    
    sections = outline['sections']
    if not sections or len(sections) == 0:
        raise ValueError("Outline must have at least one section")
    
    # Sort sections by order
    sections = sorted(sections, key=lambda s: s.get('order', 0))
    
    # Build the graph
    builder = StateGraph(GraphState)
    
    # Add standard nodes that are always needed
    builder.add_node("preprocess_node", preprocess_node)
    builder.add_node("keywords_node", keywords_node)
    builder.add_node("abstract_node", abstract_node)
    builder.add_node("plots_node", plots_node)
    builder.add_node("refine_results", refine_results)
    builder.add_node("citations_node", citations_node)
    
    # Add dynamic section nodes based on outline
    section_nodes = {}
    for section in sections:
        section_id = section.get('id', f"section_{section.get('order', 0)}")
        section_title = section.get('title', 'Section')
        section_description = section.get('description', '')
        subsections = section.get('subsections', [])
        
        # Create node for this section
        node_func = create_section_node(section_id, section_title, section_description, subsections)
        node_name = f"{section_id}_node"
        builder.add_node(node_name, node_func)
        section_nodes[section_id] = node_name
    
    # Define edges: START -> preprocess -> keywords -> abstract
    builder.add_edge(START, "preprocess_node")
    builder.add_edge("preprocess_node", "keywords_node")
    builder.add_edge("keywords_node", "abstract_node")
    
    # Connect abstract to first section
    if sections:
        first_section_id = sections[0].get('id', f"section_{sections[0].get('order', 0)}")
        first_node = section_nodes.get(first_section_id)
        if first_node:
            builder.add_edge("abstract_node", first_node)
    
    # Connect sections in order
    for i in range(len(sections) - 1):
        current_section_id = sections[i].get('id', f"section_{sections[i].get('order', 0)}")
        next_section_id = sections[i + 1].get('id', f"section_{sections[i + 1].get('order', 0)}")
        
        current_node = section_nodes.get(current_section_id)
        next_node = section_nodes.get(next_section_id)
        
        if current_node and next_node:
            builder.add_edge(current_node, next_node)
    
    # Connect last section to plots -> refine_results -> citations
    if sections:
        last_section_id = sections[-1].get('id', f"section_{sections[-1].get('order', 0)}")
        last_node = section_nodes.get(last_section_id)
        if last_node:
            builder.add_edge(last_node, "plots_node")
            builder.add_edge("plots_node", "refine_results")
            builder.add_conditional_edges("refine_results", citation_router)
            builder.add_edge("citations_node", END)
    
    # Compile graph
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    
    # Generate mermaid diagram if requested
    if mermaid_diagram:
        try:
            import requests
            original_post = requests.post

            def patched_post(*args, **kwargs):
                kwargs.setdefault("timeout", 30)
                return original_post(*args, **kwargs)

            requests.post = patched_post
            graph_image = graph.get_graph(xray=True).draw_mermaid_png()
            with open("graph_diagram.png", "wb") as f:
                f.write(graph_image)
            print("✅ Graph diagram saved to graph_diagram.png")
        except Exception as e:
            print(f"⚠️ Failed to generate or save graph diagram: {e}")
    
    return graph

