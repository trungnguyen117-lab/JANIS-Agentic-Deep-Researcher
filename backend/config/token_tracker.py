"""Simple Python-only token usage tracker using LangChain callbacks."""

import os
from typing import Dict, Optional
from threading import Lock
from pathlib import Path
from datetime import datetime
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.messages import BaseMessage

# Log file path - write to project root
_project_root = Path(__file__).parent.parent.parent.parent
LOG_FILE = _project_root / "token_usage.log"

def _write_to_log(message: str):
    """Write message to log file."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"[TokenTracker] Failed to write to log file: {e}")

# Initialize log file
try:
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("=== Token Usage Log ===\n")
            f.write(f"Log file path: {LOG_FILE}\n")
            f.write(f"Log file initialized at: {datetime.now().isoformat()}\n\n")
except Exception as e:
    print(f"[TokenTracker] Failed to initialize log file: {e}")


class TokenUsageTracker:
    """Thread-safe token usage tracker."""
    
    def __init__(self):
        self._lock = Lock()
        self._usage: Dict[str, Dict[str, int]] = {}
        # Format: {thread_id: {input: int, output: int, completion: int, reasoning: int, total: int}}
    
    def add_usage(
        self,
        thread_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
    ):
        """Add token usage for a thread."""
        with self._lock:
            if thread_id not in self._usage:
                self._usage[thread_id] = {
                    "input": 0,
                    "output": 0,
                    "completion": 0,
                    "reasoning": 0,
                    "total": 0,
                }
            
            self._usage[thread_id]["input"] += input_tokens
            self._usage[thread_id]["output"] += output_tokens
            self._usage[thread_id]["completion"] += completion_tokens
            self._usage[thread_id]["reasoning"] += reasoning_tokens
            self._usage[thread_id]["total"] += input_tokens + output_tokens
            
            # Log to file
            total = input_tokens + output_tokens
            if total > 0:  # Only log if there are actual tokens
                log_msg = (
                    f"Thread: {thread_id} | "
                    f"Input: {input_tokens} | "
                    f"Output: {output_tokens} | "
                    f"Completion: {completion_tokens} | "
                    f"Reasoning: {reasoning_tokens} | "
                    f"Total: {total} | "
                    f"Cumulative - Input: {self._usage[thread_id]['input']} | "
                    f"Output: {self._usage[thread_id]['output']} | "
                    f"Total: {self._usage[thread_id]['total']}"
                )
                _write_to_log(log_msg)
    
    def get_usage(self, thread_id: str) -> Dict[str, int]:
        """Get token usage for a thread."""
        with self._lock:
            return self._usage.get(thread_id, {
                "input": 0,
                "output": 0,
                "completion": 0,
                "reasoning": 0,
                "total": 0,
            })
    
    def reset(self, thread_id: Optional[str] = None):
        """Reset usage for a thread or all threads."""
        with self._lock:
            if thread_id:
                self._usage.pop(thread_id, None)
            else:
                self._usage.clear()


# Global token tracker instance
_token_tracker = TokenUsageTracker()


def get_token_tracker() -> TokenUsageTracker:
    """Get the global token tracker instance."""
    return _token_tracker


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler to track token usage."""
    
    def __init__(self, thread_id: Optional[str] = None):
        """Initialize callback handler.
        
        Args:
            thread_id: Optional thread ID to associate usage with.
                      If None, will try to extract from run context.
        """
        super().__init__()
        self.thread_id = thread_id
        self.tracker = get_token_tracker()
    
    def on_llm_end(self, response: LLMResult, **kwargs: any) -> None:
        """Called when LLM finishes running.
        
        Extracts token usage from LLMResult and stores it.
        """
        # Try to get thread_id from run context if not set
        thread_id = self.thread_id
        
        # Try to extract from kwargs (LangGraph/LangChain context)
        if not thread_id:
            # LangGraph uses 'run_id' or 'parent_run_id' in kwargs
            run_id = kwargs.get("run_id") or kwargs.get("parent_run_id")
            if run_id:
                # Use run_id as thread identifier
                # Note: In LangGraph, you may need to map run_id to thread_id
                thread_id = str(run_id)
        
        # Also try to get from run_manager if available
        if not thread_id:
            run_manager = kwargs.get("run_manager")
            if run_manager and hasattr(run_manager, "run_id"):
                thread_id = str(run_manager.run_id)
        
        if not thread_id:
            # Fallback: use a default thread
            thread_id = "default"
        
        # Extract token usage from LLMResult
        # LLMResult has llm_output which contains token_usage
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage", {})
        
        # Also check generations for usage_metadata
        input_tokens = 0
        output_tokens = 0
        completion_tokens = 0
        reasoning_tokens = 0
        
        # Try to get from token_usage dict (OpenAI format)
        if token_usage:
            input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0)
            output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0)
            
            # Check for reasoning tokens
            if "completion_tokens_details" in token_usage:
                reasoning_tokens = token_usage["completion_tokens_details"].get("reasoning_tokens", 0)
            elif "output_token_details" in token_usage:
                reasoning_tokens = token_usage["output_token_details"].get("reasoning", 0)
        
        # Also check each generation's message for usage_metadata
        for generation_list in response.generations:
            for generation in generation_list:
                if hasattr(generation, "message") and hasattr(generation.message, "usage_metadata"):
                    usage_meta = generation.message.usage_metadata
                    if usage_meta:
                        # usage_metadata is a dict or object with input_tokens, output_tokens
                        if isinstance(usage_meta, dict):
                            input_tokens += usage_meta.get("input_tokens", 0)
                            output_tokens += usage_meta.get("output_tokens", 0)
                            
                            # Check for reasoning tokens
                            output_details = usage_meta.get("output_token_details", {})
                            if isinstance(output_details, dict):
                                reasoning_tokens += output_details.get("reasoning", 0)
                        else:
                            # It's an object with attributes
                            input_tokens += getattr(usage_meta, "input_tokens", 0)
                            output_tokens += getattr(usage_meta, "output_tokens", 0)
                            
                            # Check for reasoning tokens
                            output_details = getattr(usage_meta, "output_token_details", None)
                            if output_details:
                                reasoning_tokens += getattr(output_details, "reasoning", 0) if hasattr(output_details, "reasoning") else 0
                
                # Also check response_metadata
                if hasattr(generation, "message") and hasattr(generation.message, "response_metadata"):
                    resp_meta = generation.message.response_metadata
                    if resp_meta and "token_usage" in resp_meta:
                        token_usage_meta = resp_meta["token_usage"]
                        if isinstance(token_usage_meta, dict):
                            input_tokens += token_usage_meta.get("prompt_tokens", 0) or token_usage_meta.get("input_tokens", 0)
                            output_tokens += token_usage_meta.get("completion_tokens", 0) or token_usage_meta.get("output_tokens", 0)
                            
                            # Check for reasoning tokens
                            if "completion_tokens_details" in token_usage_meta:
                                reasoning_tokens += token_usage_meta["completion_tokens_details"].get("reasoning_tokens", 0)
        
        # Calculate completion tokens (output - reasoning)
        completion_tokens = max(0, output_tokens - reasoning_tokens)
        
        # Log raw extraction for debugging
        if input_tokens > 0 or output_tokens > 0:
            _write_to_log(
                f"EXTRACTED - Thread: {thread_id} | "
                f"From llm_output.token_usage: {token_usage} | "
                f"Input: {input_tokens} | Output: {output_tokens} | "
                f"Completion: {completion_tokens} | Reasoning: {reasoning_tokens}"
            )
            
            # Also log full LLMResult for debugging
            _write_to_log(f"FULL LLMResult.llm_output: {response.llm_output}")
            if response.generations:
                for i, gen_list in enumerate(response.generations):
                    for j, gen in enumerate(gen_list):
                        if hasattr(gen, "message"):
                            msg = gen.message
                            _write_to_log(
                                f"Generation [{i}][{j}] - "
                                f"Has usage_metadata: {hasattr(msg, 'usage_metadata')} | "
                                f"Has response_metadata: {hasattr(msg, 'response_metadata')}"
                            )
                            if hasattr(msg, "usage_metadata"):
                                _write_to_log(f"  usage_metadata: {msg.usage_metadata}")
                            if hasattr(msg, "response_metadata"):
                                _write_to_log(f"  response_metadata: {msg.response_metadata}")
        
        # Only add if we have some tokens
        if input_tokens > 0 or output_tokens > 0:
            self.tracker.add_usage(
                thread_id=thread_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
            )
        else:
            # Log when no tokens found for debugging
            _write_to_log(
                f"NO TOKENS FOUND - Thread: {thread_id} | "
                f"llm_output: {response.llm_output} | "
                f"generations count: {len(response.generations)}"
            )

