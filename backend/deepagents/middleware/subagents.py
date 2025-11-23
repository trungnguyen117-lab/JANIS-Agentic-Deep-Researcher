"""Middleware for providing subagents to an agent via a `task` tool."""

from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from typing import Any, NotRequired, TypedDict, cast

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain.tools import BaseTool, ToolRuntime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.types import Command, Overwrite


class SubAgent(TypedDict):
    """Specification for an agent.

    When specifying custom agents, the `default_middleware` from `SubAgentMiddleware`
    will be applied first, followed by any `middleware` specified in this spec.
    To use only custom middleware without the defaults, pass `default_middleware=[]`
    to `SubAgentMiddleware`.
    """

    name: str
    """The name of the agent."""

    description: str
    """The description of the agent."""

    system_prompt: str
    """The system prompt to use for the agent."""

    tools: Sequence[BaseTool | Callable | dict[str, Any]]
    """The tools to use for the agent."""

    model: NotRequired[str | BaseChatModel]
    """The model for the agent. Defaults to `default_model`."""

    middleware: NotRequired[list[AgentMiddleware]]
    """Additional middleware to append after `default_middleware`."""

    interrupt_on: NotRequired[dict[str, bool | InterruptOnConfig]]
    """The tool configs to use for the agent."""


class CompiledSubAgent(TypedDict):
    """A pre-compiled agent spec."""

    name: str
    """The name of the agent."""

    description: str
    """The description of the agent."""

    runnable: Runnable
    """The Runnable to use for the agent."""


DEFAULT_SUBAGENT_PROMPT = "In order to complete the objective that the user asks of you, you have access to a number of standard tools."

# State keys that should be excluded when passing state to subagents
_EXCLUDED_STATE_KEYS = ("messages", "todos")

TASK_TOOL_DESCRIPTION = """Launch an ephemeral subagent to handle complex, multi-step independent tasks with isolated context windows.

Available agent types and the tools they have access to:
{available_agents}

When using the Task tool, you must specify a subagent_type parameter to select which agent type to use.

## Usage notes:
1. Launch multiple agents concurrently whenever possible, to maximize performance; to do that, use a single message with multiple tool uses
2. When the agent is done, it will return a single message back to you. The result returned by the agent is not visible to the user. To show the user the result, you should send a text message back to the user with a concise summary of the result.
3. Each agent invocation is stateless. You will not be able to send additional messages to the agent, nor will the agent be able to communicate with you outside of its final report. Therefore, your prompt should contain a highly detailed task description for the agent to perform autonomously and you should specify exactly what information the agent should return back to you in its final and only message to you.
4. The agent's outputs should generally be trusted
5. Clearly tell the agent whether you expect it to create content, perform analysis, or just do research (search, file reads, web fetches, etc.), since it is not aware of the user's intent
6. If the agent description mentions that it should be used proactively, then you should try your best to use it without the user having to ask for it first. Use your judgement.
7. When only the general-purpose agent is provided, you should use it for all tasks. It is great for isolating context and token usage, and completing specific, complex tasks, as it has all the same capabilities as the main agent.

### Example usage of the general-purpose agent:

<example_agent_descriptions>
"general-purpose": use this agent for general purpose tasks, it has access to all tools as the main agent.
</example_agent_descriptions>

<example>
User: "I want to conduct research on the accomplishments of Lebron James, Michael Jordan, and Kobe Bryant, and then compare them."
Assistant: *Uses the task tool in parallel to conduct isolated research on each of the three players*
Assistant: *Synthesizes the results of the three isolated research tasks and responds to the User*
<commentary>
Research is a complex, multi-step task in it of itself.
The research of each individual player is not dependent on the research of the other players.
The assistant uses the task tool to break down the complex objective into three isolated tasks.
Each research task only needs to worry about context and tokens about one player, then returns synthesized information about each player as the Tool Result.
This means each research task can dive deep and spend tokens and context deeply researching each player, but the final result is synthesized information, and saves us tokens in the long run when comparing the players to each other.
</commentary>
</example>

<example>
User: "Analyze a single large code repository for security vulnerabilities and generate a report."
Assistant: *Launches a single `task` subagent for the repository analysis*
Assistant: *Receives report and integrates results into final summary*
<commentary>
Subagent is used to isolate a large, context-heavy task, even though there is only one. This prevents the main thread from being overloaded with details.
If the user then asks followup questions, we have a concise report to reference instead of the entire history of analysis and tool calls, which is good and saves us time and money.
</commentary>
</example>

<example>
User: "Schedule two meetings for me and prepare agendas for each."
Assistant: *Calls the task tool in parallel to launch two `task` subagents (one per meeting) to prepare agendas*
Assistant: *Returns final schedules and agendas*
<commentary>
Tasks are simple individually, but subagents help silo agenda preparation.
Each subagent only needs to worry about the agenda for one meeting.
</commentary>
</example>

<example>
User: "I want to order a pizza from Dominos, order a burger from McDonald's, and order a salad from Subway."
Assistant: *Calls tools directly in parallel to order a pizza from Dominos, a burger from McDonald's, and a salad from Subway*
<commentary>
The assistant did not use the task tool because the objective is super simple and clear and only requires a few trivial tool calls.
It is better to just complete the task directly and NOT use the `task`tool.
</commentary>
</example>

### Example usage with custom agents:

<example_agent_descriptions>
"content-reviewer": use this agent after you are done creating significant content or documents
"greeting-responder": use this agent when to respond to user greetings with a friendly joke
"research-analyst": use this agent to conduct thorough research on complex topics
</example_agent_description>

<example>
user: "Please write a function that checks if a number is prime"
assistant: Sure let me write a function that checks if a number is prime
assistant: First let me use the Write tool to write a function that checks if a number is prime
assistant: I'm going to use the Write tool to write the following code:
<code>
function isPrime(n) {{
  if (n <= 1) return false
  for (let i = 2; i * i <= n; i++) {{
    if (n % i === 0) return false
  }}
  return true
}}
</code>
<commentary>
Since significant content was created and the task was completed, now use the content-reviewer agent to review the work
</commentary>
assistant: Now let me use the content-reviewer agent to review the code
assistant: Uses the Task tool to launch with the content-reviewer agent
</example>

<example>
user: "Can you help me research the environmental impact of different renewable energy sources and create a comprehensive report?"
<commentary>
This is a complex research task that would benefit from using the research-analyst agent to conduct thorough analysis
</commentary>
assistant: I'll help you research the environmental impact of renewable energy sources. Let me use the research-analyst agent to conduct comprehensive research on this topic.
assistant: Uses the Task tool to launch with the research-analyst agent, providing detailed instructions about what research to conduct and what format the report should take
</example>

<example>
user: "Hello"
<commentary>
Since the user is greeting, use the greeting-responder agent to respond with a friendly joke
</commentary>
assistant: "I'm going to use the Task tool to launch with the greeting-responder agent"
</example>"""  # noqa: E501

TASK_SYSTEM_PROMPT = """## `task` (subagent spawner)

You have access to a `task` tool to launch short-lived subagents that handle isolated tasks. These agents are ephemeral — they live only for the duration of the task and return a single result.

When to use the task tool:
- When a task is complex and multi-step, and can be fully delegated in isolation
- When a task is independent of other tasks and can run in parallel
- When a task requires focused reasoning or heavy token/context usage that would bloat the orchestrator thread
- When sandboxing improves reliability (e.g. code execution, structured searches, data formatting)
- When you only care about the output of the subagent, and not the intermediate steps (ex. performing a lot of research and then returned a synthesized report, performing a series of computations or lookups to achieve a concise, relevant answer.)

Subagent lifecycle:
1. **Spawn** → Provide clear role, instructions, and expected output
2. **Run** → The subagent completes the task autonomously
3. **Return** → The subagent provides a single structured result
4. **Reconcile** → Incorporate or synthesize the result into the main thread

When NOT to use the task tool:
- If you need to see the intermediate reasoning or steps after the subagent has completed (the task tool hides them)
- If the task is trivial (a few tool calls or simple lookup)
- If delegating does not reduce token usage, complexity, or context switching
- If splitting would add latency without benefit

## Important Task Tool Usage Notes to Remember
- Whenever possible, parallelize the work that you do. This is true for both tool_calls, and for tasks. Whenever you have independent steps to complete - make tool_calls, or kick off tasks (subagents) in parallel to accomplish them faster. This saves time for the user, which is incredibly important.
- Remember to use the `task` tool to silo independent tasks within a multi-part objective.
- You should use the `task` tool whenever you have a complex task that will take multiple steps, and is independent from other tasks that the agent needs to complete. These agents are highly competent and efficient."""  # noqa: E501


DEFAULT_GENERAL_PURPOSE_DESCRIPTION = "General-purpose agent for researching complex questions, searching for files and content, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you. This agent has access to all tools as the main agent."  # noqa: E501


def _get_subagents(
    *,
    default_model: str | BaseChatModel,
    default_tools: Sequence[BaseTool | Callable | dict[str, Any]],
    default_middleware: list[AgentMiddleware] | None,
    default_interrupt_on: dict[str, bool | InterruptOnConfig] | None,
    subagents: list[SubAgent | CompiledSubAgent],
    general_purpose_agent: bool,
) -> tuple[dict[str, Any], list[str]]:
    """Create subagent instances from specifications.

    Args:
        default_model: Default model for subagents that don't specify one.
        default_tools: Default tools for subagents that don't specify tools.
        default_middleware: Middleware to apply to all subagents. If `None`,
            no default middleware is applied.
        default_interrupt_on: The tool configs to use for the default general-purpose subagent. These
            are also the fallback for any subagents that don't specify their own tool configs.
        subagents: List of agent specifications or pre-compiled agents.
        general_purpose_agent: Whether to include a general-purpose subagent.

    Returns:
        Tuple of (agent_dict, description_list) where agent_dict maps agent names
        to runnable instances and description_list contains formatted descriptions.
    """
    # Use empty list if None (no default middleware)
    default_subagent_middleware = default_middleware or []

    agents: dict[str, Any] = {}
    subagent_descriptions = []

    # Create general-purpose agent if enabled
    if general_purpose_agent:
        general_purpose_middleware = [*default_subagent_middleware]
        if default_interrupt_on:
            general_purpose_middleware.append(HumanInTheLoopMiddleware(interrupt_on=default_interrupt_on))
        general_purpose_subagent = create_agent(
            default_model,
            system_prompt=DEFAULT_SUBAGENT_PROMPT,
            tools=default_tools,
            middleware=general_purpose_middleware,
        )
        agents["general-purpose"] = general_purpose_subagent
        subagent_descriptions.append(f"- general-purpose: {DEFAULT_GENERAL_PURPOSE_DESCRIPTION}")

    # Process custom subagents
    for agent_ in subagents:
        subagent_descriptions.append(f"- {agent_['name']}: {agent_['description']}")
        if "runnable" in agent_:
            custom_agent = cast("CompiledSubAgent", agent_)
            agents[custom_agent["name"]] = custom_agent["runnable"]
            continue
        _tools = agent_.get("tools", list(default_tools))

        subagent_model = agent_.get("model", default_model)

        _middleware = [*default_subagent_middleware, *agent_["middleware"]] if "middleware" in agent_ else [*default_subagent_middleware]

        interrupt_on = agent_.get("interrupt_on", default_interrupt_on)
        if interrupt_on:
            _middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

        agents[agent_["name"]] = create_agent(
            subagent_model,
            system_prompt=agent_["system_prompt"],
            tools=_tools,
            middleware=_middleware,
        )
    return agents, subagent_descriptions


def _create_task_tool(
    *,
    default_model: str | BaseChatModel,
    default_tools: Sequence[BaseTool | Callable | dict[str, Any]],
    default_middleware: list[AgentMiddleware] | None,
    default_interrupt_on: dict[str, bool | InterruptOnConfig] | None,
    subagents: list[SubAgent | CompiledSubAgent],
    general_purpose_agent: bool,
    task_description: str | None = None,
) -> BaseTool:
    """Create a task tool for invoking subagents.

    Args:
        default_model: Default model for subagents.
        default_tools: Default tools for subagents.
        default_middleware: Middleware to apply to all subagents.
        default_interrupt_on: The tool configs to use for the default general-purpose subagent. These
            are also the fallback for any subagents that don't specify their own tool configs.
        subagents: List of subagent specifications.
        general_purpose_agent: Whether to include general-purpose agent.
        task_description: Custom description for the task tool. If `None`,
            uses default template. Supports `{available_agents}` placeholder.

    Returns:
        A StructuredTool that can invoke subagents by type.
    """
    subagent_graphs, subagent_descriptions = _get_subagents(
        default_model=default_model,
        default_tools=default_tools,
        default_middleware=default_middleware,
        default_interrupt_on=default_interrupt_on,
        subagents=subagents,
        general_purpose_agent=general_purpose_agent,
    )
    subagent_description_str = "\n".join(subagent_descriptions)

    def _extract_subagent_tool_calls(messages: list) -> list[dict[str, Any]]:
        """Extract tool calls from sub-agent messages for frontend visualization.
        
        Args:
            messages: List of messages from sub-agent execution
            
        Returns:
            List of tool call dictionaries with name, args, id, and result (if available)
        """
        import json
        import logging
        from langchain_core.messages import ToolMessage
        
        tool_calls = []
        tool_call_results = {}  # Map tool_call_id -> result
        
        # First pass: extract tool call results from ToolMessages
        for msg in messages:
            if isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, "tool_call_id", None)
                if tool_call_id:
                    # Get result content
                    result_content = ""
                    if hasattr(msg, "content"):
                        result_content = msg.content
                    elif hasattr(msg, "text"):
                        result_content = msg.text
                    elif isinstance(msg, dict):
                        result_content = msg.get("content", msg.get("text", ""))
                    else:
                        result_content = str(msg)
                    
                    tool_call_results[tool_call_id] = result_content
        
        # Second pass: extract tool calls from AIMessages and match with results
        for idx, msg in enumerate(messages):
            if isinstance(msg, AIMessage):
                logging.info(
                    f"[SubAgent] _extract_subagent_tool_calls: Processing AIMessage {idx}, "
                    f"has_tool_calls={hasattr(msg, 'tool_calls') and bool(msg.tool_calls)}, "
                    f"tool_calls_count={len(msg.tool_calls) if hasattr(msg, 'tool_calls') and msg.tool_calls else 0}, "
                    f"has_additional_kwargs={hasattr(msg, 'additional_kwargs') and bool(msg.additional_kwargs)}"
                )
                # Extract tool calls from AI messages
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        # Handle different tool call formats
                        if isinstance(tc, dict):
                            tc_id = tc.get('id') or f"subagent-tool-{len(tool_calls)}"
                            tc_name = tc.get('name', 'unknown')
                            tc_args = tc.get('args', {})
                        else:
                            tc_id = getattr(tc, 'id', None) or f"subagent-tool-{len(tool_calls)}"
                            tc_name = getattr(tc, 'name', None) or 'unknown'
                            tc_args = getattr(tc, 'args', None) or {}
                        
                        # Parse args if it's a string (JSON)
                        if isinstance(tc_args, str):
                            try:
                                tc_args = json.loads(tc_args)
                            except (json.JSONDecodeError, TypeError):
                                pass  # Keep as string if not valid JSON
                        
                        tool_call_dict = {
                            "id": tc_id,
                            "name": tc_name,
                            "args": tc_args,
                        }
                        
                        # Add result if available
                        if tc_id in tool_call_results:
                            tool_call_dict["result"] = tool_call_results[tc_id]
                            tool_call_dict["status"] = "completed"
                        else:
                            tool_call_dict["status"] = "pending"
                        
                        tool_calls.append(tool_call_dict)
                
                # Also check additional_kwargs for tool_calls
                if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                    if 'tool_calls' in msg.additional_kwargs:
                        for tc in msg.additional_kwargs['tool_calls']:
                            tc_id = tc.get('id') or f"subagent-tool-{len(tool_calls)}"
                            tc_name = tc.get('function', {}).get('name') or tc.get('name', 'unknown')
                            tc_args = tc.get('function', {}).get('arguments') or tc.get('args', {})
                            
                            # Parse args if it's a string (JSON)
                            if isinstance(tc_args, str):
                                try:
                                    tc_args = json.loads(tc_args)
                                except (json.JSONDecodeError, TypeError):
                                    pass  # Keep as string if not valid JSON
                            
                            tool_call_dict = {
                                "id": tc_id,
                                "name": tc_name,
                                "args": tc_args,
                            }
                            
                            # Add result if available
                            if tc_id in tool_call_results:
                                tool_call_dict["result"] = tool_call_results[tc_id]
                                tool_call_dict["status"] = "completed"
                            else:
                                tool_call_dict["status"] = "pending"
                            
                            tool_calls.append(tool_call_dict)
        
        # Log only summary, not full details
        if not tool_calls:
            logging.warning(
                f"[SubAgent] _extract_subagent_tool_calls: No tool calls extracted from {len(messages)} messages"
        )
        
        return tool_calls

    def _serialize_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
        """Convert tool_calls payloads (objects or dicts) into serializable dicts."""
        import json
        
        if not tool_calls:
            return []
        
        serialized_calls = []
        for idx, tc in enumerate(tool_calls):
            if isinstance(tc, dict):
                tc_id = tc.get("id") or f"subagent-tool-{idx}"
                tc_name = tc.get("name") or tc.get("function", {}).get("name") or "unknown"
                tc_args = tc.get("args") or tc.get("function", {}).get("arguments") or {}
            else:
                tc_id = getattr(tc, "id", None) or f"subagent-tool-{idx}"
                tc_name = getattr(tc, "name", None)
                if not tc_name and hasattr(tc, "function"):
                    tc_name = getattr(tc.function, "name", None)
                tc_args = getattr(tc, "args", None)
                if tc_args is None and hasattr(tc, "function"):
                    tc_args = getattr(tc.function, "arguments", None)
                if tc_args is None and hasattr(tc, "json_args"):
                    tc_args = getattr(tc, "json_args", None)
            if isinstance(tc_args, str):
                try:
                    tc_args = json.loads(tc_args)
                except (json.JSONDecodeError, TypeError):
                    pass
            serialized_calls.append(
                {
                    "id": tc_id,
                    "name": tc_name or "unknown",
                    "args": tc_args if tc_args is not None else {},
                }
            )
        return serialized_calls
    
    def _strip_tool_calls_from_message(message: AIMessage) -> AIMessage:
        """Return a deep copy of the message without tool call metadata.
        
        OpenAI requires every tool_call to have a matching ToolMessage response.
        When we replay sub-agent AIMessages in the main thread we must remove
        the nested tool call payloads so the orchestrator doesn't try to satisfy
        sub-agent tool calls itself.
        """
        msg_copy = deepcopy(message)
        serialized_calls = _serialize_tool_calls(getattr(msg_copy, "tool_calls", []))
        if hasattr(msg_copy, "tool_calls"):
            msg_copy.tool_calls = []
        
        additional_kwargs = getattr(msg_copy, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict):
            additional_kwargs.pop("tool_calls", None)
            additional_kwargs.pop("function_call", None)
            msg_copy.additional_kwargs = additional_kwargs
        else:
            msg_copy.additional_kwargs = {}
        
        if serialized_calls:
            msg_copy.additional_kwargs["_subagent_tool_calls"] = serialized_calls
        
        return msg_copy
    
    def _prepare_subagent_ai_message(
        message: AIMessage,
        *,
        parent_tool_call_id: str,
        subagent_type: str | None,
    ) -> AIMessage:
        """Create a sanitized AIMessage annotated with sub-agent metadata."""
        msg_copy = _strip_tool_calls_from_message(message)
        if not hasattr(msg_copy, "additional_kwargs") or msg_copy.additional_kwargs is None:
            msg_copy.additional_kwargs = {}
        msg_copy.additional_kwargs["_subagent_source"] = {
            "tool_call_id": parent_tool_call_id,
            "subagent_type": subagent_type,
        }
        return msg_copy

    def _return_command_with_state_update(result: dict, tool_call_id: str, subagent_type: str = None, accumulated_tool_calls_map: dict = None) -> Command:
        state_update = {k: v for k, v in result.items() if k not in _EXCLUDED_STATE_KEYS}
        
        # Extract tool calls from sub-agent messages for frontend visualization
        subagent_tool_calls = []
        if "messages" in result:
            subagent_tool_calls = _extract_subagent_tool_calls(result["messages"])
            # Tool calls extracted, no need to log details
        
        # Create ToolMessage with sub-agent tool calls in additional_kwargs
        # Extract content from the last message (could be AIMessage, HumanMessage, etc.)
        # This content becomes the toolCall.result in the frontend
        tool_message_content = ""
        if result.get("messages"):
            last_msg = result["messages"][-1]
            # Try different ways to get content
            if hasattr(last_msg, "content"):
                tool_message_content = last_msg.content
            elif hasattr(last_msg, "text"):
                tool_message_content = last_msg.text
            elif isinstance(last_msg, dict):
                tool_message_content = last_msg.get("content", last_msg.get("text", ""))
            else:
                tool_message_content = str(last_msg)
        
        # If we have multiple messages, try to get a summary or the final output
        # The last message should be the final response from the sub-agent
        if not tool_message_content and result.get("messages"):
            # Try to get content from any message
            for msg in reversed(result["messages"]):
                if hasattr(msg, "content") and msg.content:
                    tool_message_content = msg.content
                    break
                elif hasattr(msg, "text") and msg.text:
                    tool_message_content = msg.text
                    break
        
        import logging
        logging.info(
            f"[SubAgent] _return_command_with_state_update: Tool message content length={len(tool_message_content)}, "
            f"has_tool_calls={len(subagent_tool_calls) > 0}, subagent_type={subagent_type}"
        )
        
        # Include sub-agent tool calls in the message metadata for frontend
        # This is critical - the frontend reads subagent_tool_calls from additional_kwargs
        additional_kwargs = {}
        if subagent_tool_calls:
            additional_kwargs["subagent_tool_calls"] = subagent_tool_calls
        if subagent_type:
            additional_kwargs["subagent_type"] = subagent_type
        
        # Always set additional_kwargs as a dict (even if empty) to ensure it's preserved
        # Some serializers might drop None values
        tool_message = ToolMessage(
            content=tool_message_content,
            tool_call_id=tool_call_id,
            additional_kwargs=additional_kwargs,  # Always pass dict, never None
        )
        
        logging.info(
            f"[SubAgent] Created ToolMessage: content_length={len(tool_message_content)}, "
            f"has_additional_kwargs={bool(additional_kwargs)}, "
            f"additional_kwargs_keys={list(additional_kwargs.keys()) if additional_kwargs else []}, "
            f"tool_call_id={tool_call_id}"
        )
        
        # Verify the ToolMessage has additional_kwargs set correctly
        if hasattr(tool_message, "additional_kwargs"):
            # additional_kwargs set correctly
            pass
        else:
            logging.warning("[SubAgent] ToolMessage does not have additional_kwargs attribute!")
        
        # CRITICAL: Only add the ToolMessage to the main thread's message history.
        # Do NOT add sub-agent AIMessages to the main thread, as this breaks OpenAI's
        # tool call validation (it expects ToolMessages immediately after AIMessages with tool_calls).
        # Sub-agent AIMessages are only used for frontend streaming via stream_writer.
        messages_to_add = [tool_message]  # Only the ToolMessage goes to main thread
        
        # Also store sub-agent tool calls in state for reliable frontend access
        # This is a fallback in case additional_kwargs is not preserved during serialization
        update_dict = {
                **state_update,
            "messages": messages_to_add,  # Only ToolMessage, no sub-agent AIMessages
        }
        
        # Store sub-agent tool calls in state with key: subagent_tool_calls_map
        # Format: {tool_call_id: {"tool_calls": [...], "subagent_type": ...}}
        # CRITICAL: Only use accumulated tool calls from THIS sub-agent invocation
        # Do NOT merge with state_update's map as it contains tool calls from ALL sub-agents
        # Each sub-agent invocation has a unique tool_call_id, so we only need its own tool calls
        tool_calls_map = {}
        if accumulated_tool_calls_map:
            # Start with accumulated tool calls from streaming (only for THIS sub-agent)
            tool_calls_map = accumulated_tool_calls_map.copy()
        else:
            # Fallback: get existing map from state_update, but ONLY for this tool_call_id
            # This ensures we don't accidentally include tool calls from other sub-agents
            existing_map = state_update.get("subagent_tool_calls_map", {})
            if isinstance(existing_map, dict) and tool_call_id in existing_map:
                # Only include the entry for THIS tool_call_id
                tool_calls_map = {tool_call_id: existing_map[tool_call_id].copy()}
            else:
                tool_calls_map = {}
        
        # CRITICAL: Build a map of tool call IDs to their ToolMessages for status updates
        # This ensures last few tools that arrived after streaming get their status updated
        tool_call_results = {}
        if "messages" in result:
            for msg in result["messages"]:
                if isinstance(msg, ToolMessage):
                    tool_call_id_from_msg = getattr(msg, "tool_call_id", None)
                    if tool_call_id_from_msg:
                        if hasattr(msg, "content"):
                            tool_call_results[tool_call_id_from_msg] = msg.content
                        elif hasattr(msg, "text"):
                            tool_call_results[tool_call_id_from_msg] = msg.text
        
        # Merge tool calls from final result (if any) with accumulated ones
        if subagent_tool_calls:
            if tool_call_id not in tool_calls_map:
                tool_calls_map[tool_call_id] = {
                    "tool_calls": [],
                    "subagent_type": subagent_type,
                }
            # Merge final tool calls (avoid duplicates by ID)
            existing_ids = {tc.get("id") for tc in tool_calls_map[tool_call_id].get("tool_calls", [])}
            new_tool_calls = [tc for tc in subagent_tool_calls if tc.get("id") not in existing_ids]
            
            # CRITICAL: Update status for new tool calls based on ToolMessages
            for tc in new_tool_calls:
                tc_id = tc.get("id")
                if tc_id in tool_call_results:
                    tc["status"] = "completed"
                    tc["result"] = tool_call_results[tc_id]
                else:
                    tc["status"] = "pending"
            
            tool_calls_map[tool_call_id]["tool_calls"].extend(new_tool_calls)
            
            # CRITICAL: Also update status for existing tool calls if ToolMessages exist
            # This ensures last few tools that arrived after streaming get their status updated
            for existing_tc in tool_calls_map[tool_call_id]["tool_calls"]:
                tc_id = existing_tc.get("id")
                if tc_id in tool_call_results and existing_tc.get("status") != "completed":
                    existing_tc["status"] = "completed"
                    existing_tc["result"] = tool_call_results[tc_id]
        
        # CRITICAL: Handle parallel sub-agents correctly
        # When multiple sub-agents run in parallel, each has a unique tool_call_id
        # We need to:
        # 1. Preserve ALL existing sub-agents' entries in the state map
        # 2. Only update/add the entry for THIS tool_call_id
        # 3. Ensure tool calls from different sub-agents don't get mixed
        if tool_calls_map:
            # Get existing map from state to preserve ALL other sub-agents' entries
            # This is critical for parallel execution - we must not overwrite other sub-agents' tool calls
            existing_state_map = state_update.get("subagent_tool_calls_map", {})
            if not isinstance(existing_state_map, dict):
                existing_state_map = {}
            
            # Merge: preserve ALL existing entries, update/add only this tool_call_id's entry
            # This ensures parallel sub-agents don't interfere with each other
            merged_map = existing_state_map.copy()
            
            # Only update/add entries from tool_calls_map (which only contains THIS sub-agent's tool calls)
            # tool_calls_map is keyed by tool_call_id, so this only affects the current sub-agent
            for key, value in tool_calls_map.items():
                # Verify this is the expected tool_call_id (safety check)
                if key == tool_call_id:
                    merged_map[key] = value
                else:
                    # This shouldn't happen, but log if it does
                    import logging
                    logging.warning(
                        f"[SubAgent] _return_command_with_state_update: Unexpected tool_call_id in map: "
                        f"expected={tool_call_id}, found={key}, subagent_type={subagent_type}"
                    )
            
            # Log to help debug tool call isolation issues, especially for parallel sub-agents
            import logging
            logging.info(
                f"[SubAgent] _return_command_with_state_update: Updating tool calls map for tool_call_id={tool_call_id}, "
                f"subagent_type={subagent_type}, "
                f"tool_calls_count={len(tool_calls_map.get(tool_call_id, {}).get('tool_calls', []))}, "
                f"existing_map_keys={list(existing_state_map.keys())}, "
                f"merged_map_keys={list(merged_map.keys())}, "
                f"parallel_subagents={len(existing_state_map) > 1}"
            )
            
            update_dict["subagent_tool_calls_map"] = merged_map
            
        
        return Command(update=update_dict)

    def _validate_and_prepare_state(subagent_type: str, description: str, runtime: ToolRuntime) -> tuple[Runnable, dict]:
        """Validate subagent type and prepare state for invocation."""
        if subagent_type not in subagent_graphs:
            msg = f"Error: invoked agent of type {subagent_type}, the only allowed types are {[f'`{k}`' for k in subagent_graphs]}"
            raise ValueError(msg)
        subagent = subagent_graphs[subagent_type]
        # Create a new state dict to avoid mutating the original
        subagent_state = {k: v for k, v in runtime.state.items() if k not in _EXCLUDED_STATE_KEYS}
        subagent_state["messages"] = [HumanMessage(content=description)]
        return subagent, subagent_state
    
    def _get_callbacks_from_runtime(runtime: ToolRuntime) -> list[Any]:
        """Extract callbacks from runtime config to pass to sub-agents.
        
        This ensures Langfuse CallbackHandler receives LLM events from sub-agents
        so token usage can be tracked.
        
        Tries multiple sources:
        1. runtime.config.callbacks (if available)
        2. runtime.config.get("callbacks") (if config is a dict)
        3. Langfuse handler directly (if configured)
        """
        callbacks = []
        try:
            # Try to get callbacks from runtime config
            if hasattr(runtime, "config") and runtime.config:
                if isinstance(runtime.config, dict):
                    callbacks = runtime.config.get("callbacks", [])
                elif hasattr(runtime.config, "callbacks"):
                    callbacks = runtime.config.callbacks or []
                # Also check configurable.callbacks (LangGraph pattern)
                if not callbacks and hasattr(runtime.config, "configurable"):
                    configurable = runtime.config.configurable
                    if isinstance(configurable, dict):
                        callbacks = configurable.get("callbacks", [])
        except Exception:
            pass
        
        # If no callbacks found in runtime, try to get Langfuse handler directly
        # This ensures Langfuse can track token usage even if callbacks aren't in runtime config
        if not callbacks:
            try:
                from backend.config.langfuse import get_langfuse_handler
                langfuse_handler = get_langfuse_handler()
                if langfuse_handler:
                    callbacks = [langfuse_handler]
            except Exception:
                pass
        
        return callbacks if isinstance(callbacks, list) else []

    # Use custom description if provided, otherwise use default template
    if task_description is None:
        task_description = TASK_TOOL_DESCRIPTION.format(available_agents=subagent_description_str)
    elif "{available_agents}" in task_description:
        # If custom description has placeholder, format with agent descriptions
        task_description = task_description.format(available_agents=subagent_description_str)

    def task(
        description: str,
        subagent_type: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        subagent, subagent_state = _validate_and_prepare_state(subagent_type, description, runtime)
        # Extract callbacks from runtime config to pass to sub-agent
        # This ensures Langfuse CallbackHandler receives LLM events from sub-agents
        callbacks = _get_callbacks_from_runtime(runtime)
        
        if not runtime.tool_call_id:
            value_error_msg = "Tool call ID is required for subagent invocation"
            raise ValueError(value_error_msg)
        
        # Use stream to get real-time updates from sub-agent (sync version - no await)
        # Stream with "updates" mode to get state updates as they happen
        final_result = None
        accumulated_messages = []
        seen_message_ids = set()
        # CRITICAL: Accumulate tool calls during streaming for THIS sub-agent only
        # Each sub-agent invocation has a unique tool_call_id (runtime.tool_call_id)
        # This map is keyed by tool_call_id, so it only contains tool calls for the current sub-agent
        # When multiple sub-agents run in parallel, each has its own accumulated_tool_calls_map
        accumulated_tool_calls_map = {}
        # CRITICAL: Accumulate tool calls during streaming for THIS sub-agent only
        # Each sub-agent invocation has a unique tool_call_id (runtime.tool_call_id)
        # This map is keyed by tool_call_id, so it only contains tool calls for the current sub-agent
        # When multiple sub-agents run in parallel, each has its own accumulated_tool_calls_map
        accumulated_tool_calls_map = {}
        
        # Use both "updates" and "values" modes to get both incremental updates and full state
        # "updates" gives us state deltas, "values" gives us full state including messages
        for chunk in subagent.stream(
            subagent_state, 
            config={"callbacks": callbacks} if callbacks else None,
            stream_mode=["updates", "values"]
        ):
            import logging
            logging.info(
                f"[SubAgent] task: Received chunk type={type(chunk).__name__}, "
                f"chunk={chunk if not isinstance(chunk, dict) or len(str(chunk)) < 500 else 'dict (too large)'}"
            )
            
            # When using multiple stream modes, chunks come as (stream_mode, chunk) tuples
            # Handle both single mode (dict) and multiple modes (tuple) formats
            stream_mode = None
            chunk_data = None
            
            if isinstance(chunk, tuple) and len(chunk) == 2:
                # Format: (stream_mode, chunk_data)
                stream_mode, chunk_data = chunk
            elif isinstance(chunk, dict):
                # Single mode: chunk is directly the data
                chunk_data = chunk
                stream_mode = "updates"  # Default assumption
            else:
                logging.warning(f"[SubAgent] task: Unknown chunk format: type={type(chunk).__name__}, chunk={chunk}")
                continue
            
            # chunk_data should be a dict like {node_name: state_update}
            if not isinstance(chunk_data, dict):
                logging.warning(f"[SubAgent] task: chunk_data is not a dict: type={type(chunk_data).__name__}")
                continue
            
            items_to_process = list(chunk_data.items())
            
            # Extract messages and tool calls from each update
            for item in items_to_process:
                if isinstance(item, tuple) and len(item) == 2:
                    node_name, state_update = item
                else:
                    continue
                    
                
                # Handle both "updates" (state deltas) and "values" (full state) modes
                # In "values" mode, chunks come as (stream_mode, {node_name: value}) where node_name is the state key
                # So if node_name is "messages", state_update IS the list of messages
                # In "updates" mode, state_update is a dict with state deltas
                if stream_mode == "values" and node_name == "messages":
                    # In values mode, when node_name is "messages", state_update IS the list of messages
                    # Handle Overwrite objects that might wrap the messages
                    messages_raw = state_update
                    
                    # Extract actual value if it's wrapped in Overwrite
                    if isinstance(messages_raw, Overwrite):
                        new_messages = messages_raw.value if hasattr(messages_raw, "value") else []
                    elif isinstance(messages_raw, dict) and "__overwrite__" in messages_raw:
                        # Handle JSON format with __overwrite__ key
                        new_messages = messages_raw["__overwrite__"]
                    else:
                        new_messages = messages_raw if isinstance(messages_raw, list) else []
                    
                    if new_messages:
                            # Filter out messages we've already seen
                            truly_new_messages = [
                                msg for msg in new_messages
                                if hasattr(msg, "id") and msg.id not in seen_message_ids
                            ]
                            if not any(hasattr(msg, "id") for msg in new_messages):
                                truly_new_messages = new_messages
                            
                            if truly_new_messages:
                                for msg in truly_new_messages:
                                    if hasattr(msg, "id") and msg.id:
                                        seen_message_ids.add(msg.id)
                                accumulated_messages.extend(truly_new_messages)
                                
                                # Extract tool calls and update state (same as async version)
                                subagent_tool_calls = _extract_subagent_tool_calls(truly_new_messages)
                                if subagent_tool_calls or any(isinstance(msg, AIMessage) for msg in truly_new_messages):
                                    try:
                                        messages_to_add_to_main = []
                                        for msg in truly_new_messages:
                                            if isinstance(msg, AIMessage):
                                                msg_copy = _prepare_subagent_ai_message(
                                                    msg,
                                                    parent_tool_call_id=runtime.tool_call_id,
                                                    subagent_type=subagent_type,
                                                )
                                                messages_to_add_to_main.append(msg_copy)
                                        
                                        current_map = {}
                                        try:
                                            if hasattr(runtime, "state") and runtime.state:
                                                current_map = runtime.state.get("subagent_tool_calls_map", {})
                                                if not isinstance(current_map, dict):
                                                    current_map = {}
                                        except Exception:
                                            pass
                                        
                                        if subagent_tool_calls:
                                            if runtime.tool_call_id not in current_map:
                                                current_map[runtime.tool_call_id] = {
                                                    "tool_calls": [],
                                                    "subagent_type": subagent_type,
                                                }
                                            existing_ids = {tc.get("id") for tc in current_map[runtime.tool_call_id].get("tool_calls", [])}
                                            new_tool_calls = [tc for tc in subagent_tool_calls if tc.get("id") not in existing_ids]
                                            current_map[runtime.tool_call_id]["tool_calls"].extend(new_tool_calls)
                                        
                                        if hasattr(runtime, "stream_writer") and runtime.stream_writer:
                                            try:
                                                stream_update = {
                                                    f"subagent_{subagent_type}_{node_name}": {
                                                        "messages": messages_to_add_to_main,
                                                        "subagent_tool_calls_map": current_map,
                                                    }
                                                }
                                                runtime.stream_writer(stream_update)
                                                logging.info(
                                                    f"[SubAgent] task: Streaming update from values mode: "
                                                    f"Added {len(messages_to_add_to_main)} messages, "
                                                    f"{len(subagent_tool_calls)} tool calls"
                                                )
                                            except Exception as e:
                                                logging.warning(f"Failed to forward sub-agent streaming update: {e}", exc_info=True)
                                    except Exception as e:
                                        logging.error(f"Failed to update state during sub-agent streaming: {e}", exc_info=True)
                    
                    # Handle "updates" mode (state deltas)
                elif stream_mode == "updates" and isinstance(state_update, dict) and "messages" in state_update:
                    # Get new messages from this update
                    # Note: state_update["messages"] might be the full list or just new messages
                    # We need to track which messages we've already seen
                    # Handle Overwrite objects that might wrap the messages
                    messages_raw = state_update.get("messages", [])
                    
                    # Extract actual value if it's wrapped in Overwrite
                    if isinstance(messages_raw, Overwrite):
                        new_messages = messages_raw.value if hasattr(messages_raw, "value") else []
                    elif isinstance(messages_raw, dict) and "__overwrite__" in messages_raw:
                        # Handle JSON format with __overwrite__ key
                        new_messages = messages_raw["__overwrite__"]
                    else:
                        new_messages = messages_raw if isinstance(messages_raw, list) else []
                    
                    if new_messages:
                        # Filter out messages we've already seen (to avoid duplicates)
                        truly_new_messages = [
                            msg for msg in new_messages
                            if hasattr(msg, "id") and msg.id not in seen_message_ids
                        ]
                        
                        # If no IDs, assume all are new (for backwards compatibility)
                        if not any(hasattr(msg, "id") for msg in new_messages):
                            truly_new_messages = new_messages
                        
                        if truly_new_messages:
                            # Track message IDs to avoid duplicates
                            for msg in truly_new_messages:
                                if hasattr(msg, "id") and msg.id:
                                    seen_message_ids.add(msg.id)
                            
                            # Add to accumulated messages
                            accumulated_messages.extend(truly_new_messages)
                            
                            # Extract tool calls from new messages
                            subagent_tool_calls = _extract_subagent_tool_calls(truly_new_messages)
                            
                            # Update state during streaming so frontend sees tool calls and results in real-time
                            # Stream ALL message types (AIMessages with tool_calls AND ToolMessages with results)
                            # Just like main agent: AIMessage → tool calls appear, ToolMessage → status updates to completed
                            if subagent_tool_calls or any(isinstance(msg, (AIMessage, ToolMessage)) for msg in truly_new_messages):
                                try:
                                    # Create messages WITH tool_calls/results for real-time display (via stream_writer)
                                    # These will appear in stream.messages and show tool calls/results as they happen
                                    messages_with_tool_calls_for_display = []
                                    # Create messages WITHOUT tool_calls for main agent's message history
                                    messages_without_tool_calls_for_history = []
                                    
                                    for msg in truly_new_messages:
                                        if isinstance(msg, AIMessage):
                                            prepared_msg = _prepare_subagent_ai_message(
                                                msg,
                                                parent_tool_call_id=runtime.tool_call_id,
                                                subagent_type=subagent_type,
                                            )
                                            messages_with_tool_calls_for_display.append(prepared_msg)
                                            messages_without_tool_calls_for_history.append(deepcopy(prepared_msg))
                                        elif isinstance(msg, ToolMessage):
                                            # ToolMessages contain results - stream them IMMEDIATELY, one at a time
                                            # Just like main agent: each ToolMessage is added to state as soon as the tool completes
                                            # This ensures real-time status updates, not batched at the end
                                            msg_copy = deepcopy(msg)
                                            # Add metadata to indicate this is from a sub-agent
                                            if not hasattr(msg_copy, "additional_kwargs") or msg_copy.additional_kwargs is None:
                                                msg_copy.additional_kwargs = {}
                                            msg_copy.additional_kwargs["_subagent_source"] = {
                                                "tool_call_id": runtime.tool_call_id,
                                                "subagent_type": subagent_type,
                                            }
                                            # Include ToolMessages in both display and history (they don't have tool_calls)
                                            messages_with_tool_calls_for_display.append(msg_copy)
                                            messages_without_tool_calls_for_history.append(msg_copy)
                                            
                                            # Stream this ToolMessage IMMEDIATELY (like main agent does)
                                            # Don't wait for other messages - stream as soon as tool completes
                                            # In sync function, no need to yield control - streaming happens synchronously
                                            if hasattr(runtime, "stream_writer") and runtime.stream_writer:
                                                try:
                                                    # Get current map for this tool_call_id
                                                    # Use a unique context copy to avoid mutating shared state
                                                    current_map_for_tool = accumulated_tool_calls_map.copy()
                                                    try:
                                                        if hasattr(runtime, "state") and runtime.state:
                                                            state_map = runtime.state.get("subagent_tool_calls_map", {})
                                                            if isinstance(state_map, dict):
                                                                for key, value in state_map.items():
                                                                    if key not in current_map_for_tool:
                                                                        current_map_for_tool[key] = value
                                                    except Exception:
                                                        pass
                                                    
                                                    # CRITICAL: Update tool call status to "completed" when ToolMessage arrives
                                                    # Extract tool_call_id from the ToolMessage
                                                    tool_call_id_from_msg = getattr(msg_copy, "tool_call_id", None)
                                                    if tool_call_id_from_msg and runtime.tool_call_id in current_map_for_tool:
                                                        # Find the tool call in the map and update its status
                                                        tool_calls_list = current_map_for_tool[runtime.tool_call_id].get("tool_calls", [])
                                                        for tc in tool_calls_list:
                                                            if tc.get("id") == tool_call_id_from_msg:
                                                                tc["status"] = "completed"
                                                                # Also add the result content
                                                                if hasattr(msg_copy, "content"):
                                                                    tc["result"] = msg_copy.content
                                                                elif hasattr(msg_copy, "text"):
                                                                    tc["result"] = msg_copy.text
                                                                break
                                                    
                                                    # Update accumulated map so subsequent streams have the updated status
                                                    accumulated_tool_calls_map = current_map_for_tool.copy()
                                                    
                                                    # Stream this single ToolMessage immediately with updated map
                                                    stream_update_immediate = {
                                                        "messages": [msg_copy],  # Stream this ONE ToolMessage immediately
                                                        "subagent_tool_calls_map": current_map_for_tool,  # Map with updated "completed" status
                                                    }
                                                    runtime.stream_writer(stream_update_immediate)
                                                except Exception as e:
                                                    import logging
                                                    logging.warning(f"Failed to stream ToolMessage immediately: {e}", exc_info=True)
                                    
                                    # Get current subagent_tool_calls_map from accumulated map and state
                                    # Use a unique context copy to avoid mutating shared state
                                    current_map = accumulated_tool_calls_map.copy()
                                    try:
                                        if hasattr(runtime, "state") and runtime.state:
                                            state_map = runtime.state.get("subagent_tool_calls_map", {})
                                            if isinstance(state_map, dict):
                                                # Merge state map into current_map
                                                for key, value in state_map.items():
                                                    if key not in current_map:
                                                        current_map[key] = value
                                    except Exception:
                                        pass
                                    
                                    # CRITICAL: Initialize map entry if it doesn't exist (needed for streaming)
                                    if runtime.tool_call_id not in current_map:
                                        current_map[runtime.tool_call_id] = {
                                            "tool_calls": [],
                                            "subagent_type": subagent_type,
                                        }
                                    
                                    # Merge new tool calls into map
                                    has_new_tool_calls = False
                                    if subagent_tool_calls:
                                        # Append new tool calls (avoid duplicates by ID)
                                        existing_ids = {tc.get("id") for tc in current_map[runtime.tool_call_id].get("tool_calls", [])}
                                        new_tool_calls = [tc for tc in subagent_tool_calls if tc.get("id") not in existing_ids]
                                        if new_tool_calls:
                                            has_new_tool_calls = True
                                            # Ensure all new tool calls have status "pending" if no result yet
                                            for tc in new_tool_calls:
                                                if "status" not in tc:
                                                    tc["status"] = "pending"
                                            current_map[runtime.tool_call_id]["tool_calls"].extend(new_tool_calls)
                                            # Update accumulated map for final state update
                                            accumulated_tool_calls_map = current_map.copy()
                                    
                                    # CRITICAL FIX: Stream AIMessages immediately when they arrive, even if tool calls aren't extracted yet
                                    # This ensures tool calls appear in the frontend as soon as they're available
                                    # ToolMessages are already streamed individually above, so we stream AIMessages here
                                    ai_messages_only = [m for m in messages_with_tool_calls_for_display if isinstance(m, AIMessage)]
                                    has_ai_messages = len(ai_messages_only) > 0
                                    
                                    # CRITICAL: Check if AIMessage has tool_calls (even if not extracted yet)
                                    # We need to stream immediately when AIMessage with tool_calls arrives, so frontend shows "spinning"
                                    has_ai_with_tool_calls = False
                                    for msg in truly_new_messages:
                                        if isinstance(msg, AIMessage):
                                            if (hasattr(msg, "tool_calls") and msg.tool_calls) or \
                                               (hasattr(msg, "additional_kwargs") and msg.additional_kwargs and 
                                                ("tool_calls" in msg.additional_kwargs or "_subagent_tool_calls" in msg.additional_kwargs)):
                                                has_ai_with_tool_calls = True
                                                break
                                    
                                    # CRITICAL: Stream if we have new tool calls OR status updates from ToolMessages
                                    # We MUST stream when ToolMessages update status, even if no new tool calls were added
                                    # This ensures tool calls transition from "pending" (spinning) to "completed" (green checkmark)
                                    should_stream_ai = (
                                        ai_messages_only and 
                                        hasattr(runtime, "stream_writer") and 
                                        runtime.stream_writer and
                                        (has_new_tool_calls or has_ai_messages or has_ai_with_tool_calls or has_tool_messages_in_batch)
                                    )
                                    
                                    if should_stream_ai:
                                        try:
                                            # Stream AIMessages with tool_calls (ToolMessages are already streamed individually above)
                                            # This matches main agent behavior: AIMessage appears first, then ToolMessages appear one by one
                                            stream_update = {
                                                "messages": ai_messages_only,  # Only AIMessages (ToolMessages streamed individually)
                                                "subagent_tool_calls_map": current_map,  # Also send the map as backup
                                            }
                                            import logging
                                            logging.info(
                                                f"[SubAgent] Streaming AIMessages with tool_calls: tool_call_id={runtime.tool_call_id}, "
                                                f"ai_messages_count={len(ai_messages_only)}, "
                                                f"new_tool_calls_count={len(new_tool_calls) if has_new_tool_calls else 0}, "
                                                f"total_tool_calls_count={len(current_map.get(runtime.tool_call_id, {}).get('tool_calls', []))}"
                                            )
                                            runtime.stream_writer(stream_update)
                                        except Exception as e:
                                            import logging
                                            logging.warning(f"Failed to forward sub-agent streaming update: {e}", exc_info=True)
                                    
                                    # Store messages WITHOUT tool_calls for final state update (for main agent's history)
                                    # These will be added to the main thread's message history at the end to avoid OpenAI errors
                                    if messages_without_tool_calls_for_history:
                                        # Replace accumulated messages with versions without tool_calls for this tool_call_id
                                        # This ensures the main agent's history doesn't have incomplete tool call sequences
                                        pass  # We'll handle this in the final state update
                                except Exception as e:
                                    import logging
                                    logging.error(f"Failed to update state during sub-agent streaming: {e}", exc_info=True)
                
                # Track final result (merge with accumulated state)
                if isinstance(state_update, dict):
                    if final_result is None:
                        final_result = state_update.copy()
                    else:
                        # Merge state updates (messages will be handled separately)
                        for key, value in state_update.items():
                            if key != "messages":
                                final_result[key] = value
                    
                    # Update final result with accumulated messages
                    if accumulated_messages:
                        final_result["messages"] = accumulated_messages
        
        # If we didn't get a final result, use the last state update
        if final_result is None:
            # Fallback to invoke if streaming didn't work
            final_result = subagent.invoke(subagent_state, config={"callbacks": callbacks} if callbacks else None)
        
        # Ensure messages are in final_result
        if final_result and "messages" not in final_result:
            if accumulated_messages:
                final_result["messages"] = accumulated_messages
            else:
                # If no accumulated messages, try to get from final_result state
                import logging
                logging.warning(
                    f"[SubAgent] task: No messages in final_result and no accumulated_messages. "
                    f"final_result keys: {list(final_result.keys()) if isinstance(final_result, dict) else 'not a dict'}"
                )
        
        import logging
        logging.info(
            f"[SubAgent] task: Final result has {len(final_result.get('messages', []))} messages, "
            f"accumulated_messages has {len(accumulated_messages)} messages, "
            f"subagent_type={subagent_type}, tool_call_id={runtime.tool_call_id}"
        )
        
        return _return_command_with_state_update(final_result, runtime.tool_call_id, subagent_type=subagent_type, accumulated_tool_calls_map=accumulated_tool_calls_map)

    async def atask(
        description: str,
        subagent_type: str,
        runtime: ToolRuntime,
    ) -> str | Command:
        subagent, subagent_state = _validate_and_prepare_state(subagent_type, description, runtime)
        # Extract callbacks from runtime config to pass to sub-agent
        # This ensures Langfuse CallbackHandler receives LLM events from sub-agents
        callbacks = _get_callbacks_from_runtime(runtime)
        
        if not runtime.tool_call_id:
            value_error_msg = "Tool call ID is required for subagent invocation"
            raise ValueError(value_error_msg)
        
        # Use astream to get real-time updates from sub-agent
        # Stream with "updates" mode to get state updates as they happen
        final_result = None
        accumulated_messages = []
        seen_message_ids = set()
        # CRITICAL: Accumulate tool calls during streaming for THIS sub-agent only
        # Each sub-agent invocation has a unique tool_call_id (runtime.tool_call_id)
        # This map is keyed by tool_call_id, so it only contains tool calls for the current sub-agent
        # When multiple sub-agents run in parallel, each has its own accumulated_tool_calls_map
        accumulated_tool_calls_map = {}
        
        # Use both "updates" and "values" modes to get both incremental updates and full state
        # "updates" gives us state deltas, "values" gives us full state including messages
        async for chunk in subagent.astream(
            subagent_state, 
            config={"callbacks": callbacks} if callbacks else None,
            stream_mode=["updates", "values"]
        ):
            import logging
            logging.info(
                f"[SubAgent] atask: Received chunk type={type(chunk).__name__}, "
                f"chunk={chunk if not isinstance(chunk, dict) or len(str(chunk)) < 500 else 'dict (too large)'}"
            )
            
            # When using multiple stream modes, chunks come as (stream_mode, chunk) tuples
            # Handle both single mode (dict) and multiple modes (tuple) formats
            stream_mode = None
            chunk_data = None
            
            if isinstance(chunk, tuple) and len(chunk) == 2:
                # Format: (stream_mode, chunk_data)
                stream_mode, chunk_data = chunk
            elif isinstance(chunk, dict):
                # Single mode: chunk is directly the data
                chunk_data = chunk
                stream_mode = "updates"  # Default assumption
            else:
                logging.warning(f"[SubAgent] atask: Unknown chunk format: type={type(chunk).__name__}, chunk={chunk}")
                continue
            
            # chunk_data should be a dict like {node_name: state_update}
            if not isinstance(chunk_data, dict):
                logging.warning(f"[SubAgent] atask: chunk_data is not a dict: type={type(chunk_data).__name__}")
                continue
            
            items_to_process = list(chunk_data.items())
            
            # Extract messages and tool calls from each update
            # In "values" mode, we get full state; in "updates" mode, we get state deltas
            for item in items_to_process:
                if isinstance(item, tuple) and len(item) == 2:
                    node_name, state_update = item
                else:
                    continue
                    
                
                # Handle both "updates" (state deltas) and "values" (full state) modes
                # In "values" mode, chunks come as (stream_mode, {node_name: value}) where node_name is the state key
                # So if node_name is "messages", state_update IS the list of messages
                # In "updates" mode, state_update is a dict with state deltas
                if stream_mode == "values" and node_name == "messages":
                    # In values mode, when node_name is "messages", state_update IS the list of messages
                    # Handle Overwrite objects that might wrap the messages
                    messages_raw = state_update
                    
                    # Extract actual value if it's wrapped in Overwrite
                    if isinstance(messages_raw, Overwrite):
                        new_messages = messages_raw.value if hasattr(messages_raw, "value") else []
                    elif isinstance(messages_raw, dict) and "__overwrite__" in messages_raw:
                        # Handle JSON format with __overwrite__ key
                        new_messages = messages_raw["__overwrite__"]
                    else:
                        new_messages = messages_raw if isinstance(messages_raw, list) else []
                    
                    if new_messages:
                        # Filter out messages we've already seen
                        truly_new_messages = [
                            msg for msg in new_messages
                            if hasattr(msg, "id") and msg.id not in seen_message_ids
                        ]
                        
                        # If no IDs, assume all are new
                        if not any(hasattr(msg, "id") for msg in new_messages):
                            truly_new_messages = new_messages
                        
                        if truly_new_messages:
                            # Track message IDs
                            for msg in truly_new_messages:
                                if hasattr(msg, "id") and msg.id:
                                    seen_message_ids.add(msg.id)
                            
                            # Add to accumulated messages
                            accumulated_messages.extend(truly_new_messages)
                            
                            # Get current subagent_tool_calls_map from accumulated map and state FIRST
                            # This is needed before we process messages to update their status
                            current_map = accumulated_tool_calls_map.copy()
                            try:
                                if hasattr(runtime, "state") and runtime.state:
                                    state_map = runtime.state.get("subagent_tool_calls_map", {})
                                    if isinstance(state_map, dict):
                                        # Merge state map into current_map
                                        for key, value in state_map.items():
                                            if key not in current_map:
                                                current_map[key] = value
                            except Exception:
                                pass
                            
                            # CRITICAL: Initialize map entry if it doesn't exist (needed for streaming)
                            if runtime.tool_call_id not in current_map:
                                current_map[runtime.tool_call_id] = {
                                    "tool_calls": [],
                                    "subagent_type": subagent_type,
                                }
                            
                            # CRITICAL: Extract tool calls from AIMessages ONLY first (to get "pending" status)
                            # Then we'll update to "completed" when ToolMessages arrive
                            ai_messages_only = [msg for msg in truly_new_messages if isinstance(msg, AIMessage)]
                            subagent_tool_calls_from_ai = _extract_subagent_tool_calls(ai_messages_only) if ai_messages_only else []
                            
                            # ALWAYS send updates for new messages to enable real-time streaming
                            # This ensures frontend sees messages as they arrive, not just at the end
                            try:
                                messages_with_tool_calls_for_display = []
                                messages_without_tool_calls_for_history = []
                                
                                # Process messages for display
                                for msg in truly_new_messages:
                                    if isinstance(msg, AIMessage):
                                        prepared_msg = _prepare_subagent_ai_message(
                                            msg,
                                            parent_tool_call_id=runtime.tool_call_id,
                                            subagent_type=subagent_type,
                                        )
                                        messages_with_tool_calls_for_display.append(prepared_msg)
                                        messages_without_tool_calls_for_history.append(deepcopy(prepared_msg))
                                    elif isinstance(msg, ToolMessage):
                                        # ToolMessages should also be included for real-time display
                                        msg_copy = deepcopy(msg)
                                        if not hasattr(msg_copy, "additional_kwargs") or msg_copy.additional_kwargs is None:
                                            msg_copy.additional_kwargs = {}
                                        msg_copy.additional_kwargs["_subagent_source"] = {
                                            "tool_call_id": runtime.tool_call_id,
                                            "subagent_type": subagent_type,
                                        }
                                        messages_with_tool_calls_for_display.append(msg_copy)
                                        messages_without_tool_calls_for_history.append(msg_copy)
                                
                                # CRITICAL: First, add tool calls from AIMessages with "pending" status
                                # This ensures tool calls show as "spinning" when they first appear
                                has_new_tool_calls = False
                                if subagent_tool_calls_from_ai:
                                    # Append new tool calls (avoid duplicates by ID)
                                    existing_ids = {tc.get("id") for tc in current_map[runtime.tool_call_id].get("tool_calls", [])}
                                    new_tool_calls = [tc for tc in subagent_tool_calls_from_ai if tc.get("id") not in existing_ids]
                                    if new_tool_calls:
                                        has_new_tool_calls = True
                                        # Force all new tool calls to "pending" status (they come from AIMessages)
                                        for tc in new_tool_calls:
                                            tc["status"] = "pending"
                                            # Remove result if present (shouldn't be, but just in case)
                                            tc.pop("result", None)
                                        current_map[runtime.tool_call_id]["tool_calls"].extend(new_tool_calls)
                                        # Update accumulated map for final state update
                                        accumulated_tool_calls_map = current_map.copy()
                                
                                # CRITICAL: Then, update status of tool calls to "completed" when ToolMessages arrive
                                # This ensures tool calls transition from "pending" (spinning) to "completed" (green checkmark)
                                has_tool_messages = False
                                status_updated = False
                                for msg in truly_new_messages:
                                    if isinstance(msg, ToolMessage):
                                        has_tool_messages = True
                                        tool_call_id_from_msg = getattr(msg, "tool_call_id", None)
                                        if tool_call_id_from_msg and runtime.tool_call_id in current_map:
                                            tool_calls_list = current_map[runtime.tool_call_id].get("tool_calls", [])
                                            for tc in tool_calls_list:
                                                if tc.get("id") == tool_call_id_from_msg:
                                                    # Only update if status is not already "completed" (avoid unnecessary updates)
                                                    if tc.get("status") != "completed":
                                                        tc["status"] = "completed"
                                                        status_updated = True
                                                    # Also add the result content
                                                    if hasattr(msg, "content"):
                                                        tc["result"] = msg.content
                                                    elif hasattr(msg, "text"):
                                                        tc["result"] = msg.text
                                                    break
                                
                                # Update accumulated map after status updates
                                if has_tool_messages and status_updated:
                                    accumulated_tool_calls_map = current_map.copy()
                                
                                # CRITICAL FIX: ALWAYS stream messages when they arrive, even if tool calls aren't extracted yet
                                # This ensures AIMessages appear immediately in the frontend, and tool calls appear as soon as they're extracted
                                # The frontend will show tool calls as "pending" initially, then update to "completed" when ToolMessages arrive
                                has_ai_messages = any(isinstance(m, AIMessage) for m in messages_with_tool_calls_for_display)
                                
                                # CRITICAL: Check if AIMessage has tool_calls (even if not extracted yet)
                                # We need to stream immediately when AIMessage with tool_calls arrives, so frontend shows "spinning"
                                has_ai_with_tool_calls = False
                                for msg in truly_new_messages:
                                    if isinstance(msg, AIMessage):
                                        if (hasattr(msg, "tool_calls") and msg.tool_calls) or \
                                           (hasattr(msg, "additional_kwargs") and msg.additional_kwargs and 
                                            ("tool_calls" in msg.additional_kwargs or "_subagent_tool_calls" in msg.additional_kwargs)):
                                            has_ai_with_tool_calls = True
                                            break
                                
                                # CRITICAL: Stream if we have new tool calls OR status updates from ToolMessages
                                # We MUST stream when ToolMessages update status, even if no new tool calls were added
                                # This ensures tool calls transition from "pending" (spinning) to "completed" (green checkmark)
                                # status_updated indicates that tool call statuses were changed to "completed"
                                should_stream = (
                                    messages_with_tool_calls_for_display and 
                                    hasattr(runtime, "stream_writer") and 
                                    runtime.stream_writer and
                                    (has_new_tool_calls or has_tool_messages or has_ai_messages or has_ai_with_tool_calls or status_updated)
                                )
                                
                                if should_stream:
                                    try:
                                        # Add messages WITH tool_calls/results to the messages state for real-time display
                                        # These will appear in stream.messages and the frontend will:
                                        # 1. Extract tool calls from AIMessages (status: "pending") - shows as spinning
                                        # 2. Update tool call status when ToolMessages arrive (status: "completed") - shows as green checkmark
                                        # CRITICAL: Always include the updated map, even if only status changed (not new tool calls)
                                        stream_update = {
                                            "messages": messages_with_tool_calls_for_display,  # Messages WITH tool_calls/results for real-time display
                                            "subagent_tool_calls_map": current_map,  # Map with updated statuses (pending → completed)
                                        }
                                        import logging
                                        logging.info(
                                            f"[SubAgent] atask: Streaming messages (AIMessages + ToolMessages) from values mode: "
                                            f"tool_call_id={runtime.tool_call_id}, "
                                            f"messages_count={len(messages_with_tool_calls_for_display)}, "
                                            f"ai_messages={sum(1 for m in messages_with_tool_calls_for_display if isinstance(m, AIMessage))}, "
                                            f"tool_messages={sum(1 for m in messages_with_tool_calls_for_display if isinstance(m, ToolMessage))}, "
                                            f"has_tool_messages={has_tool_messages}, "
                                            f"new_tool_calls_count={len(new_tool_calls) if has_new_tool_calls else 0}, "
                                            f"total_tool_calls_count={len(current_map.get(runtime.tool_call_id, {}).get('tool_calls', []))}"
                                        )
                                        runtime.stream_writer(stream_update)
                                    except Exception as e:
                                        import logging
                                        logging.warning(f"Failed to forward sub-agent streaming update: {e}", exc_info=True)
                                
                                # Store messages WITHOUT tool_calls for final state update (for main agent's history)
                                # These will be added to the main thread's message history at the end to avoid OpenAI errors
                                if messages_without_tool_calls_for_history:
                                    # Replace accumulated messages with versions without tool_calls for this tool_call_id
                                    # This ensures the main agent's history doesn't have incomplete tool call sequences
                                    pass  # We'll handle this in the final state update
                            except Exception as e:
                                import logging
                                logging.error(f"Failed to update state during sub-agent streaming: {e}", exc_info=True)
                    
                    # Handle "updates" mode (state deltas)
                    elif stream_mode == "updates" and isinstance(state_update, dict) and "messages" in state_update:
                    # Get new messages from this update
                    # Note: state_update["messages"] might be the full list or just new messages
                    # We need to track which messages we've already seen
                        # Handle Overwrite objects that might wrap the messages
                        messages_raw = state_update.get("messages", [])
                        
                        # Extract actual value if it's wrapped in Overwrite
                        if isinstance(messages_raw, Overwrite):
                            new_messages = messages_raw.value if hasattr(messages_raw, "value") else []
                        elif isinstance(messages_raw, dict) and "__overwrite__" in messages_raw:
                            # Handle JSON format with __overwrite__ key
                            new_messages = messages_raw["__overwrite__"]
                        else:
                            new_messages = messages_raw if isinstance(messages_raw, list) else []
                        
                    if new_messages:
                        # Filter out messages we've already seen (to avoid duplicates)
                        truly_new_messages = [
                            msg for msg in new_messages
                            if hasattr(msg, "id") and msg.id not in seen_message_ids
                        ]
                        
                        # If no IDs, assume all are new (for backwards compatibility)
                        if not any(hasattr(msg, "id") for msg in new_messages):
                            truly_new_messages = new_messages
                        
                        if truly_new_messages:
                            # Track message IDs to avoid duplicates
                            for msg in truly_new_messages:
                                if hasattr(msg, "id") and msg.id:
                                    seen_message_ids.add(msg.id)
                            
                            # Add to accumulated messages
                            accumulated_messages.extend(truly_new_messages)
                            
                            # Get current subagent_tool_calls_map from accumulated map and state FIRST
                            current_map = accumulated_tool_calls_map.copy()
                            try:
                                if hasattr(runtime, "state") and runtime.state:
                                    state_map = runtime.state.get("subagent_tool_calls_map", {})
                                    if isinstance(state_map, dict):
                                        # Merge state map into current_map
                                        for key, value in state_map.items():
                                            if key not in current_map:
                                                current_map[key] = value
                            except Exception:
                                pass
                            
                            # CRITICAL: Initialize map entry if it doesn't exist (needed for streaming)
                            if runtime.tool_call_id not in current_map:
                                current_map[runtime.tool_call_id] = {
                                    "tool_calls": [],
                                    "subagent_type": subagent_type,
                                }
                            
                            # CRITICAL: Extract tool calls from AIMessages ONLY first (to get "pending" status)
                            # Then we'll update to "completed" when ToolMessages arrive
                            ai_messages_only = [msg for msg in truly_new_messages if isinstance(msg, AIMessage)]
                            subagent_tool_calls_from_ai = _extract_subagent_tool_calls(ai_messages_only) if ai_messages_only else []
                            
                            # Update state during streaming so frontend sees tool calls and results in real-time
                            # Stream ALL message types (AIMessages with tool_calls AND ToolMessages with results)
                            # Just like main agent: AIMessage → tool calls appear, ToolMessage → status updates to completed
                            if subagent_tool_calls_from_ai or any(isinstance(msg, (AIMessage, ToolMessage)) for msg in truly_new_messages):
                                try:
                                    messages_with_tool_calls_for_display = []
                                    messages_without_tool_calls_for_history = []
                                    
                                    # CRITICAL: First, add tool calls from AIMessages with "pending" status
                                    # This ensures tool calls show as "spinning" when they first appear
                                    has_new_tool_calls = False
                                    if subagent_tool_calls_from_ai:
                                        # Append new tool calls (avoid duplicates by ID)
                                        existing_ids = {tc.get("id") for tc in current_map[runtime.tool_call_id].get("tool_calls", [])}
                                        new_tool_calls = [tc for tc in subagent_tool_calls_from_ai if tc.get("id") not in existing_ids]
                                        if new_tool_calls:
                                            has_new_tool_calls = True
                                            # Force all new tool calls to "pending" status (they come from AIMessages)
                                            for tc in new_tool_calls:
                                                tc["status"] = "pending"
                                                # Remove result if present (shouldn't be, but just in case)
                                                tc.pop("result", None)
                                            current_map[runtime.tool_call_id]["tool_calls"].extend(new_tool_calls)
                                            # Update accumulated map for final state update
                                            accumulated_tool_calls_map = current_map.copy()
                                    
                                    for msg in truly_new_messages:
                                        if isinstance(msg, AIMessage):
                                            prepared_msg = _prepare_subagent_ai_message(
                                                msg,
                                                parent_tool_call_id=runtime.tool_call_id,
                                                subagent_type=subagent_type,
                                            )
                                            messages_with_tool_calls_for_display.append(prepared_msg)
                                            messages_without_tool_calls_for_history.append(deepcopy(prepared_msg))
                                        elif isinstance(msg, ToolMessage):
                                            # ToolMessages contain results - stream them IMMEDIATELY, one at a time
                                            # Just like main agent: each ToolMessage is added to state as soon as the tool completes
                                            # This ensures real-time status updates, not batched at the end
                                            msg_copy = deepcopy(msg)
                                            # Add metadata to indicate this is from a sub-agent
                                            if not hasattr(msg_copy, "additional_kwargs") or msg_copy.additional_kwargs is None:
                                                msg_copy.additional_kwargs = {}
                                            msg_copy.additional_kwargs["_subagent_source"] = {
                                                "tool_call_id": runtime.tool_call_id,
                                                "subagent_type": subagent_type,
                                            }
                                            # Include ToolMessages in both display and history (they don't have tool_calls)
                                            messages_with_tool_calls_for_display.append(msg_copy)
                                            messages_without_tool_calls_for_history.append(msg_copy)
                                            
                                            # Stream this ToolMessage IMMEDIATELY (like main agent does)
                                            # Don't wait for other messages - stream as soon as tool completes
                                            # Use asyncio.sleep(0) to yield control and ensure each ToolMessage is processed separately
                                            if hasattr(runtime, "stream_writer") and runtime.stream_writer:
                                                try:
                                                    # Get current map for this tool_call_id
                                                    current_map_for_tool = accumulated_tool_calls_map.copy()
                                                    try:
                                                        if hasattr(runtime, "state") and runtime.state:
                                                            state_map = runtime.state.get("subagent_tool_calls_map", {})
                                                            if isinstance(state_map, dict):
                                                                for key, value in state_map.items():
                                                                    if key not in current_map_for_tool:
                                                                        current_map_for_tool[key] = value
                                                    except Exception:
                                                        pass
                                                    
                                                    # CRITICAL: Update tool call status to "completed" when ToolMessage arrives
                                                    # Extract tool_call_id from the ToolMessage
                                                    tool_call_id_from_msg = getattr(msg_copy, "tool_call_id", None)
                                                    if tool_call_id_from_msg and runtime.tool_call_id in current_map_for_tool:
                                                        # Find the tool call in the map and update its status
                                                        tool_calls_list = current_map_for_tool[runtime.tool_call_id].get("tool_calls", [])
                                                        for tc in tool_calls_list:
                                                            if tc.get("id") == tool_call_id_from_msg:
                                                                tc["status"] = "completed"
                                                                # Also add the result content
                                                                if hasattr(msg_copy, "content"):
                                                                    tc["result"] = msg_copy.content
                                                                elif hasattr(msg_copy, "text"):
                                                                    tc["result"] = msg_copy.text
                                                                break
                                                    
                                                    # Update accumulated map so subsequent streams have the updated status
                                                    accumulated_tool_calls_map = current_map_for_tool.copy()
                                                    
                                                    # Stream this single ToolMessage immediately with updated map
                                                    stream_update_immediate = {
                                                        "messages": [msg_copy],  # Stream this ONE ToolMessage immediately
                                                        "subagent_tool_calls_map": current_map_for_tool,  # Map with updated "completed" status
                                                    }
                                                    runtime.stream_writer(stream_update_immediate)
                                                    
                                                    # Yield control to ensure this ToolMessage is processed before the next one
                                                    # This ensures real-time streaming like the main agent
                                                    import asyncio
                                                    await asyncio.sleep(0)
                                                except Exception as e:
                                                    import logging
                                                    logging.warning(f"Failed to stream ToolMessage immediately: {e}", exc_info=True)
                                    
                                    # CRITICAL: Update status of existing tool calls when ToolMessages arrive in batch
                                    # This ensures tool calls transition from "pending" to "completed"
                                    has_tool_messages_in_batch = False
                                    for msg in truly_new_messages:
                                        if isinstance(msg, ToolMessage):
                                            has_tool_messages_in_batch = True
                                            tool_call_id_from_msg = getattr(msg, "tool_call_id", None)
                                            if tool_call_id_from_msg and runtime.tool_call_id in current_map:
                                                tool_calls_list = current_map[runtime.tool_call_id].get("tool_calls", [])
                                                for tc in tool_calls_list:
                                                    if tc.get("id") == tool_call_id_from_msg:
                                                        tc["status"] = "completed"
                                                        # Also add the result content
                                                        if hasattr(msg, "content"):
                                                            tc["result"] = msg.content
                                                        elif hasattr(msg, "text"):
                                                            tc["result"] = msg.text
                                                        break
                                    
                                    # Update accumulated map after status updates
                                    if has_tool_messages_in_batch:
                                        accumulated_tool_calls_map = current_map.copy()
                                    
                                    # CRITICAL: Add tool calls from AIMessages with "pending" status (if not already added)
                                    # This ensures tool calls show as "spinning" when they first appear
                                    has_new_tool_calls = False
                                    if subagent_tool_calls_from_ai:
                                        # Append new tool calls (avoid duplicates by ID)
                                        existing_ids = {tc.get("id") for tc in current_map[runtime.tool_call_id].get("tool_calls", [])}
                                        new_tool_calls = [tc for tc in subagent_tool_calls_from_ai if tc.get("id") not in existing_ids]
                                        if new_tool_calls:
                                            has_new_tool_calls = True
                                            # Force all new tool calls to "pending" status (they come from AIMessages)
                                            for tc in new_tool_calls:
                                                tc["status"] = "pending"
                                                # Remove result if present (shouldn't be, but just in case)
                                                tc.pop("result", None)
                                            current_map[runtime.tool_call_id]["tool_calls"].extend(new_tool_calls)
                                            # Update accumulated map for final state update
                                            accumulated_tool_calls_map = current_map.copy()
                                    
                                    # CRITICAL FIX: Stream AIMessages immediately when they arrive, even if tool calls aren't extracted yet
                                    # This ensures tool calls appear in the frontend as soon as they're available
                                    # ToolMessages are already streamed individually above, so we stream AIMessages here
                                    ai_messages_only = [m for m in messages_with_tool_calls_for_display if isinstance(m, AIMessage)]
                                    has_ai_messages = len(ai_messages_only) > 0
                                    
                                    # CRITICAL: Check if AIMessage has tool_calls (even if not extracted yet)
                                    # We need to stream immediately when AIMessage with tool_calls arrives, so frontend shows "spinning"
                                    has_ai_with_tool_calls = False
                                    for msg in truly_new_messages:
                                        if isinstance(msg, AIMessage):
                                            if (hasattr(msg, "tool_calls") and msg.tool_calls) or \
                                               (hasattr(msg, "additional_kwargs") and msg.additional_kwargs and 
                                                ("tool_calls" in msg.additional_kwargs or "_subagent_tool_calls" in msg.additional_kwargs)):
                                                has_ai_with_tool_calls = True
                                                break
                                    
                                    # CRITICAL: Stream if we have new tool calls OR status updates from ToolMessages
                                    # We MUST stream when ToolMessages update status, even if no new tool calls were added
                                    # This ensures tool calls transition from "pending" (spinning) to "completed" (green checkmark)
                                    should_stream_ai = (
                                        ai_messages_only and 
                                        hasattr(runtime, "stream_writer") and 
                                        runtime.stream_writer and
                                        (has_new_tool_calls or has_ai_messages or has_ai_with_tool_calls or has_tool_messages_in_batch)
                                    )
                                    
                                    if should_stream_ai:
                                        try:
                                            # Stream AIMessages with tool_calls (ToolMessages are already streamed individually above)
                                            # This matches main agent behavior: AIMessage appears first, then ToolMessages appear one by one
                                            stream_update = {
                                                "messages": ai_messages_only,  # Only AIMessages (ToolMessages streamed individually)
                                                "subagent_tool_calls_map": current_map,  # Also send the map as backup
                                            }
                                            import logging
                                            logging.info(
                                                f"[SubAgent] Streaming AIMessages with tool_calls: tool_call_id={runtime.tool_call_id}, "
                                                f"ai_messages_count={len(ai_messages_only)}, "
                                                f"new_tool_calls_count={len(new_tool_calls) if has_new_tool_calls else 0}, "
                                                f"total_tool_calls_count={len(current_map.get(runtime.tool_call_id, {}).get('tool_calls', []))}"
                                            )
                                            runtime.stream_writer(stream_update)
                                        except Exception as e:
                                            import logging
                                            logging.warning(f"Failed to forward sub-agent streaming update: {e}", exc_info=True)
                                    
                                    # Store messages WITHOUT tool_calls for final state update (for main agent's history)
                                    # These will be added to the main thread's message history at the end to avoid OpenAI errors
                                    if messages_without_tool_calls_for_history:
                                        # Replace accumulated messages with versions without tool_calls for this tool_call_id
                                        # This ensures the main agent's history doesn't have incomplete tool call sequences
                                        pass  # We'll handle this in the final state update
                                except Exception as e:
                                    import logging
                                    logging.error(f"Failed to update state during sub-agent streaming: {e}", exc_info=True)
                
                # Track final result (merge with accumulated state)
                if isinstance(state_update, dict):
                    if final_result is None:
                        final_result = state_update.copy()
                    else:
                        # Merge state updates (messages will be handled separately)
                        for key, value in state_update.items():
                            if key != "messages":
                                final_result[key] = value
                    
                    # Update final result with accumulated messages
                    if accumulated_messages:
                        final_result["messages"] = accumulated_messages
        
        # If we didn't get a final result, use the last state update
        if final_result is None:
            # Fallback to ainvoke if streaming didn't work
            final_result = await subagent.ainvoke(subagent_state, config={"callbacks": callbacks} if callbacks else None)
        
        # Ensure messages are in final_result
        if final_result and "messages" not in final_result:
            if accumulated_messages:
                final_result["messages"] = accumulated_messages
            else:
                # If no accumulated messages, try to get from final_result state
                import logging
                logging.warning(
                    f"[SubAgent] atask: No messages in final_result and no accumulated_messages. "
                    f"final_result keys: {list(final_result.keys()) if isinstance(final_result, dict) else 'not a dict'}"
                )
        
        
        return _return_command_with_state_update(final_result, runtime.tool_call_id, subagent_type=subagent_type, accumulated_tool_calls_map=accumulated_tool_calls_map)

    return StructuredTool.from_function(
        name="task",
        func=task,
        coroutine=atask,
        description=task_description,
    )


class SubAgentMiddleware(AgentMiddleware):
    """Middleware for providing subagents to an agent via a `task` tool.

    This  middleware adds a `task` tool to the agent that can be used to invoke subagents.
    Subagents are useful for handling complex tasks that require multiple steps, or tasks
    that require a lot of context to resolve.

    A chief benefit of subagents is that they can handle multi-step tasks, and then return
    a clean, concise response to the main agent.

    Subagents are also great for different domains of expertise that require a narrower
    subset of tools and focus.

    This middleware comes with a default general-purpose subagent that can be used to
    handle the same tasks as the main agent, but with isolated context.

    Args:
        default_model: The model to use for subagents.
            Can be a LanguageModelLike or a dict for init_chat_model.
        default_tools: The tools to use for the default general-purpose subagent.
        default_middleware: Default middleware to apply to all subagents. If `None` (default),
            no default middleware is applied. Pass a list to specify custom middleware.
        default_interrupt_on: The tool configs to use for the default general-purpose subagent. These
            are also the fallback for any subagents that don't specify their own tool configs.
        subagents: A list of additional subagents to provide to the agent.
        system_prompt: Full system prompt override. When provided, completely replaces
            the agent's system prompt.
        general_purpose_agent: Whether to include the general-purpose agent. Defaults to `True`.
        task_description: Custom description for the task tool. If `None`, uses the
            default description template.

    Example:
        ```python
        from langchain.agents.middleware.subagents import SubAgentMiddleware
        from langchain.agents import create_agent

        # Basic usage with defaults (no default middleware)
        agent = create_agent(
            "openai:gpt-4o",
            middleware=[
                SubAgentMiddleware(
                    default_model="openai:gpt-4o",
                    subagents=[],
                )
            ],
        )

        # Add custom middleware to subagents
        agent = create_agent(
            "openai:gpt-4o",
            middleware=[
                SubAgentMiddleware(
                    default_model="openai:gpt-4o",
                    default_middleware=[TodoListMiddleware()],
                    subagents=[],
                )
            ],
        )
        ```
    """

    def __init__(
        self,
        *,
        default_model: str | BaseChatModel,
        default_tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
        default_middleware: list[AgentMiddleware] | None = None,
        default_interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
        subagents: list[SubAgent | CompiledSubAgent] | None = None,
        system_prompt: str | None = TASK_SYSTEM_PROMPT,
        general_purpose_agent: bool = True,
        task_description: str | None = None,
    ) -> None:
        """Initialize the SubAgentMiddleware."""
        super().__init__()
        self.system_prompt = system_prompt
        task_tool = _create_task_tool(
            default_model=default_model,
            default_tools=default_tools or [],
            default_middleware=default_middleware,
            default_interrupt_on=default_interrupt_on,
            subagents=subagents or [],
            general_purpose_agent=general_purpose_agent,
            task_description=task_description,
        )
        self.tools = [task_tool]

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Update the system prompt to include instructions on using subagents."""
        if self.system_prompt is not None:
            request.system_prompt = request.system_prompt + "\n\n" + self.system_prompt if request.system_prompt else self.system_prompt
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """(async) Update the system prompt to include instructions on using subagents."""
        if self.system_prompt is not None:
            request.system_prompt = request.system_prompt + "\n\n" + self.system_prompt if request.system_prompt else self.system_prompt
        return await handler(request)
