import { useCallback, useMemo, useEffect, useRef, useState } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import { getDeployment } from "@/lib/environment/deployments";
import { v4 as uuidv4 } from "uuid";
import type { TodoItem } from "../types/types";
import { createClient } from "@/lib/client";
import { useAuthContext } from "@/providers/Auth";
import { extractFileContent } from "../utils/fileContentUtils";

type StateType = {
  messages: Message[];
  todos: TodoItem[];
  files: Record<string, string>;
  token_usage?: {
    input: number;
    output: number;
    completion: number;
    reasoning: number;
    cache?: number;
    prompt?: number;
    total: number;
    cost: number;
  };
  available_models?: Array<{
    name: string;
    input_price_per_million: number;
    output_price_per_million: number;
  }>;
  subagent_tool_calls_map?: Record<string, {
    tool_calls: any[];
    subagent_type?: string;
  }>;
};

export function useChat(
  threadId: string | null,
  setThreadId: (
    value: string | ((old: string | null) => string | null) | null,
  ) => void,
  onTodosUpdate: (todos: TodoItem[]) => void,
  onFilesUpdate: (files: Record<string, string>) => void,
  onTokenUsageUpdate?: (usage: { input: number; output: number; completion: number; reasoning: number; cache?: number; prompt?: number; total: number; cost?: number }) => void,
  onModelsUpdate?: (models: Array<{ name: string; input_price_per_million: number; output_price_per_million: number }>) => void,
  selectedModel?: string, // Model selected by user (only used on first message)
) {
  const deployment = useMemo(() => getDeployment(), []);
  const { session } = useAuthContext();
  const accessToken = session?.accessToken;

  const agentId = useMemo(() => {
    if (!deployment?.agentId) {
      throw new Error(`No agent ID configured in environment`);
    }
    return deployment.agentId;
  }, [deployment]);

  const normalizeFileContent = useCallback((content: any): string => {
    // Use utility function to extract content from deepagents format
    return extractFileContent(content);
  }, []);

  // Track if we've received real-time token usage updates to prevent useEffect from overriding them
  const hasReceivedRealTimeUpdate = useRef(false);
  // Track previous token usage to prevent infinite loops
  const previousTokenUsageRef = useRef<string | null>(null);
  // Store the callback in a ref to avoid dependency issues
  const onTokenUsageUpdateRef = useRef(onTokenUsageUpdate);
  
  // Local state for subagent_tool_calls_map to enable real-time updates
  // This is merged with stream.values.subagent_tool_calls_map
  const [localSubagentToolCallsMap, setLocalSubagentToolCallsMap] = useState<Record<string, {
    tool_calls: any[];
    subagent_type?: string;
  }>>({});
  
  // Local state for sub-agent messages with tool_calls for real-time display
  // These come via stream_writer and need to be merged with stream.messages
  const [localSubagentMessages, setLocalSubagentMessages] = useState<Message[]>([]);
  
  // Update the ref when the callback changes
  useEffect(() => {
    onTokenUsageUpdateRef.current = onTokenUsageUpdate;
  }, [onTokenUsageUpdate]);

    const handleCustomEvent = useCallback(
      (data: any) => {
        // Handle custom events from stream_writer
        // These contain subagent_tool_calls_map updates and messages with tool_calls for real-time streaming
        console.log("[useChat] handleCustomEvent received:", {
          hasData: !!data,
          dataKeys: data ? Object.keys(data) : [],
          hasMessages: !!data?.messages,
          messagesCount: data?.messages?.length || 0,
          hasSubagentToolCallsMap: !!data?.subagent_tool_calls_map,
          subagentToolCallsMapKeys: data?.subagent_tool_calls_map ? Object.keys(data.subagent_tool_calls_map) : [],
        });
        
        // Handle messages with tool_calls for real-time display
        // These are sub-agent AIMessages that should appear in stream.messages
        if (data?.messages && Array.isArray(data.messages) && data.messages.length > 0) {
          console.log("[useChat] Received sub-agent messages with tool_calls:", {
            messagesCount: data.messages.length,
            messageIds: data.messages.map((m: any) => m.id),
          });
          // Merge new messages into local state, avoiding duplicates by message ID
          setLocalSubagentMessages(prev => {
            const existingIds = new Set(prev.map(m => m.id));
            const newMessages = data.messages.filter((m: any) => m.id && !existingIds.has(m.id));
            if (newMessages.length > 0) {
              console.log("[useChat] Adding new sub-agent messages to local state:", {
                newCount: newMessages.length,
                totalCount: prev.length + newMessages.length,
              });
              return [...prev, ...newMessages];
            }
            return prev;
          });
        }
        
        // Check if this is a subagent_tool_calls_map update
        if (data?.subagent_tool_calls_map) {
          console.log("[useChat] Merging subagent_tool_calls_map from custom event:", {
            newKeys: Object.keys(data.subagent_tool_calls_map),
            toolCallIds: Object.keys(data.subagent_tool_calls_map),
          });
          // Merge subagent_tool_calls_map into local state for real-time updates
          setLocalSubagentToolCallsMap(prev => {
            const merged = {
              ...prev,
              ...data.subagent_tool_calls_map,
            };
            console.log("[useChat] Merged subagent_tool_calls_map:", {
              previousKeys: Object.keys(prev),
              newKeys: Object.keys(data.subagent_tool_calls_map),
              mergedKeys: Object.keys(merged),
            });
            return merged;
          });
        }
      },
      [],
    );

    const handleUpdateEvent = useCallback(
      (data: { [node: string]: Partial<StateType> }) => {
        // Debug: Log all update events to see what we're receiving
        console.log("[useChat] handleUpdateEvent called with data:", {
          nodeNames: Object.keys(data),
          dataKeys: Object.keys(data).map(key => ({
            key,
            hasTokenUsage: !!data[key]?.token_usage,
            tokenUsage: data[key]?.token_usage,
          })),
          fullData: data,
        });
        
        Object.entries(data).forEach(([nodeName, nodeData]) => {
        if (nodeData?.todos) {
          onTodosUpdate(nodeData.todos);
        }
        
        // Handle sub-agent streaming updates
        // Sub-agent updates come via stream_writer as custom data
        // They contain messages and subagent_tool_calls_map updates
        // We need to merge subagent_tool_calls_map into local state for real-time updates
        if (nodeData?.subagent_tool_calls_map) {
          // Merge subagent_tool_calls_map into local state for real-time updates
          // This ensures the frontend sees tool calls as they're generated, not just at the end
          setLocalSubagentToolCallsMap(prev => ({
            ...prev,
            ...nodeData.subagent_tool_calls_map,
          }));
        }
        
        // Also check for subagent_ prefixed node names (legacy format)
        if (nodeName.startsWith("subagent_") && nodeData?.subagent_tool_calls_map) {
          // If this node has subagent_tool_calls_map, merge it
          setLocalSubagentToolCallsMap(prev => ({
            ...prev,
            ...nodeData.subagent_tool_calls_map,
          }));
        }
        
        // Handle token usage updates from ANY node that includes token_usage
        // This is the PRIMARY source for real-time token usage updates
        // Token usage can come from any node, not just __token_usage_update__
        console.log("[useChat] Processing node:", {
          nodeName,
          hasTokenUsage: !!nodeData?.token_usage,
          tokenUsage: nodeData?.token_usage,
          nodeDataKeys: nodeData ? Object.keys(nodeData) : [],
          isTokenUsageUpdate: nodeName === "__token_usage_update__",
        });
        
        // Check for token_usage in ANY node data (not just __token_usage_update__)
        if (nodeData?.token_usage && onTokenUsageUpdate) {
          console.log("[useChat] Received token usage update from stream_writer:", {
            input: nodeData.token_usage.input,
            output: nodeData.token_usage.output,
            total: nodeData.token_usage.total,
            cost: nodeData.token_usage.cost,
            cache: nodeData.token_usage.cache,
            prompt: nodeData.token_usage.prompt,
            completion: nodeData.token_usage.completion,
            reasoning: nodeData.token_usage.reasoning,
            fullData: nodeData.token_usage,
          });
          // Update immediately - this is the real-time update
          // Mark that we've received a real-time update to prevent useEffect from overriding
          hasReceivedRealTimeUpdate.current = true;
          
          const tokenUsage = {
            input: nodeData.token_usage.input || 0,
            output: nodeData.token_usage.output || 0,
            completion: nodeData.token_usage.completion || 0,
            reasoning: nodeData.token_usage.reasoning || 0,
            cache: nodeData.token_usage.cache || 0,
            prompt: nodeData.token_usage.prompt || 0,
            total: nodeData.token_usage.total || 0,
            cost: nodeData.token_usage.cost || 0,
          };
          
          // Check if this is different from previous to prevent unnecessary updates
          const usageString = JSON.stringify(tokenUsage);
          if (previousTokenUsageRef.current !== usageString && onTokenUsageUpdateRef.current) {
            previousTokenUsageRef.current = usageString;
            onTokenUsageUpdateRef.current(tokenUsage);
          }
        }
        
        // Also check if token_usage is in the nodeData directly (fallback)
        if (nodeData?.token_usage && onTokenUsageUpdateRef.current && nodeName !== "__token_usage_update__") {
          console.log("[useChat] Received token usage in nodeData:", {
            nodeName,
            input: nodeData.token_usage.input,
            output: nodeData.token_usage.output,
            total: nodeData.token_usage.total,
          });
          
          const tokenUsage = {
            input: nodeData.token_usage.input || 0,
            output: nodeData.token_usage.output || 0,
            completion: nodeData.token_usage.completion || 0,
            reasoning: nodeData.token_usage.reasoning || 0,
            cache: nodeData.token_usage.cache || 0,
            prompt: nodeData.token_usage.prompt || 0,
            total: nodeData.token_usage.total || 0,
            cost: nodeData.token_usage.cost || 0,
          };
          
          // Check if this is different from previous to prevent unnecessary updates
          const usageString = JSON.stringify(tokenUsage);
          if (previousTokenUsageRef.current !== usageString) {
            previousTokenUsageRef.current = usageString;
            onTokenUsageUpdateRef.current(tokenUsage);
          }
        }
        
        // Handle sub-agent updates from stream_writer
        // These come as custom events with subagent_* node names
        if (nodeName.startsWith("subagent_") && nodeData) {
          // Sub-agent updates are processed when the ToolMessage arrives
          // The stream_writer events are just for real-time visibility
          // The actual tool calls are in the ToolMessage's additional_kwargs
        }
        
        if (nodeData?.available_models && onModelsUpdate) {
          onModelsUpdate(nodeData.available_models);
        }
          if (nodeData?.files !== undefined) {
            // Check if files is an empty object - this might indicate files were cleared
            if (nodeData.files && Object.keys(nodeData.files).length === 0) {
              console.warn("[handleUpdateEvent] Received empty files object - this might clear files. Ignoring empty update.");
              // Don't process empty file updates that might clear existing files
              // Continue processing other updates (like todos) from other nodes
            } else if (nodeData.files) {
              // Normalize file content to ensure all values are strings
              const normalizedFiles: Record<string, string> = {};
              Object.entries(nodeData.files).forEach(([path, content]) => {
                // Only process if content is not null/undefined
                if (content !== null && content !== undefined) {
                  normalizedFiles[path] = normalizeFileContent(content);
                }
              });
              // Only update if we have files to add/update
              if (Object.keys(normalizedFiles).length > 0) {
                // Note: onFilesUpdate should merge with existing files, not replace them
                // This is handled in page.tsx by using functional setState
                onFilesUpdate(normalizedFiles);
              } else {
                console.warn("[handleUpdateEvent] No valid files to update after normalization");
              }
            }
          }
      });
    },
    [onTodosUpdate, onFilesUpdate, normalizeFileContent, onModelsUpdate, onTokenUsageUpdate],
  );

  const stream = useStream<StateType>({
    assistantId: agentId,
    client: createClient(accessToken || ""),
    reconnectOnMount: !!threadId, // Only reconnect if we have a threadId
    threadId: threadId ?? null,
    onUpdateEvent: handleUpdateEvent,
    onCustomEvent: handleCustomEvent, // Handle custom events from stream_writer
    onThreadId: setThreadId,
    defaultHeaders: {
      "x-auth-scheme": "langsmith",
    },
  });
  
  // Watch stream.values.token_usage directly for real-time updates
  // stream_writer updates might go directly to stream.values, not through onUpdateEvent
  // This is the PRIMARY way to get real-time token usage updates
  // We watch the entire stream.values object because nested property changes might not trigger updates
  useEffect(() => {
    // Debug: Log stream.values to see what we have
    console.log("[useChat] stream.values changed:", {
      hasValues: !!stream.values,
      valuesKeys: stream.values ? Object.keys(stream.values) : [],
      hasTokenUsage: !!stream.values?.token_usage,
      tokenUsage: stream.values?.token_usage,
      fullValues: stream.values,
    });
    
    if (!onTokenUsageUpdateRef.current) return;
    
    const usage = stream.values?.token_usage;
    
    // Create a string representation to compare
    const usageString = usage ? JSON.stringify({
      input: usage.input || 0,
      output: usage.output || 0,
      completion: usage.completion || 0,
      reasoning: usage.reasoning || 0,
      cache: usage.cache || 0,
      prompt: usage.prompt || 0,
      total: usage.total || 0,
      cost: usage.cost || 0,
    }) : JSON.stringify({
      input: 0,
      output: 0,
      completion: 0,
      reasoning: 0,
      cache: 0,
      prompt: 0,
      total: 0,
      cost: 0,
    });
    
    // Only update if it's different from previous
    if (previousTokenUsageRef.current !== usageString) {
      // Check if this is a meaningful update (non-zero values or explicit zero reset)
      const hasNonZeroValues = (usage?.input || 0) > 0 || (usage?.output || 0) > 0 || (usage?.total || 0) > 0;
      
      // Only log and update if we have non-zero values OR if this is the first update
      if (hasNonZeroValues || previousTokenUsageRef.current === null) {
        console.log("[useChat] stream.values.token_usage changed:", {
          usage,
          input: usage?.input,
          output: usage?.output,
          total: usage?.total,
          cost: usage?.cost,
          previousString: previousTokenUsageRef.current,
          newString: usageString,
          streamValuesKeys: stream.values ? Object.keys(stream.values) : [],
          hasNonZeroValues,
        });
        
        previousTokenUsageRef.current = usageString;
        hasReceivedRealTimeUpdate.current = true; // Mark as received
        
        onTokenUsageUpdateRef.current({
          input: usage?.input || 0,
          output: usage?.output || 0,
          completion: usage?.completion || 0,
          reasoning: usage?.reasoning || 0,
          cache: usage?.cache || 0,
          prompt: usage?.prompt || 0,
          total: usage?.total || 0,
          cost: usage?.cost || 0,
        });
      } else {
        // Still update the ref to prevent re-processing, but don't call the callback
        previousTokenUsageRef.current = usageString;
      }
    }
  }, [stream.values]); // Watch entire stream.values object - nested property changes should trigger this

  const sendMessage = useCallback(
    (message: string) => {
      const humanMessage: Message = {
        id: uuidv4(),
        type: "human",
        content: message,
      };
      
      // Check if this is the first message (no previous messages)
      const isFirstMessage = stream.messages.length === 0;
      
      // Build config - include model selection only on first message
      const config: any = {
        recursion_limit: 200, // Increased to handle improvement loops for multiple sections
      };
      
      // Only pass model selection on first message
      if (isFirstMessage && selectedModel) {
        config.configurable = {
          model: selectedModel,
        };
      }
      
      stream.submit(
        { messages: [humanMessage] },
        {
          optimisticValues(prev) {
            const prevMessages = prev.messages ?? [];
            const newMessages = [...prevMessages, humanMessage];
            return { ...prev, messages: newMessages };
          },
          config,
        },
      );
    },
    [stream, selectedModel],
  );

  const stopStream = useCallback(() => {
    stream.stop();
  }, [stream]);

  // Read token usage from state - thread-isolated (FALLBACK only)
  // NOTE: Real-time updates come via handleUpdateEvent (stream_writer events)
  // This useEffect is only for initial load and when thread changes
  useEffect(() => {
    if (!onTokenUsageUpdateRef.current) return;
    
    // Read token usage directly from state (thread-isolated)
    // This is a fallback for when stream_writer updates aren't available
    const usage = stream.values?.token_usage;
    
    // Create a string representation of the usage to compare
    const usageString = usage ? JSON.stringify({
      input: usage.input || 0,
      output: usage.output || 0,
      completion: usage.completion || 0,
      reasoning: usage.reasoning || 0,
      cache: usage.cache || 0,
      prompt: usage.prompt || 0,
      total: usage.total || 0,
      cost: usage.cost || 0,
    }) : JSON.stringify({
      input: 0,
      output: 0,
      completion: 0,
      reasoning: 0,
      cache: 0,
      prompt: 0,
      total: 0,
      cost: 0,
    });
    
    // Only update if the usage has actually changed
    if (previousTokenUsageRef.current === usageString) {
      return; // Skip if same as previous
    }
    
    console.log("[useChat] useEffect: Reading token usage from stream.values (fallback):", {
      usage,
      hasUsage: !!usage,
      input: usage?.input,
      output: usage?.output,
      total: usage?.total,
      cost: usage?.cost,
      hasReceivedRealTimeUpdate: hasReceivedRealTimeUpdate.current,
      streamValuesKeys: stream.values ? Object.keys(stream.values) : [],
      usageChanged: previousTokenUsageRef.current !== usageString,
    });
    
    // Only update from stream.values if we haven't received real-time updates
    // OR if this is a thread change (threadId changed)
    if (usage && (!hasReceivedRealTimeUpdate.current || threadId)) {
      const tokenUsage = {
        input: usage.input || 0,
        output: usage.output || 0,
        completion: usage.completion || 0,
        reasoning: usage.reasoning || 0,
        cache: usage.cache || 0,
        prompt: usage.prompt || 0,
        total: usage.total || 0,
        cost: usage.cost || 0,
      };
      previousTokenUsageRef.current = usageString;
      onTokenUsageUpdateRef.current(tokenUsage);
    } else if (!usage && !hasReceivedRealTimeUpdate.current) {
      // No token usage in state yet - set to zero (only if no real-time updates received)
      previousTokenUsageRef.current = usageString;
      onTokenUsageUpdateRef.current({
        input: 0,
        output: 0,
        completion: 0,
        reasoning: 0,
        cache: 0,
        prompt: 0,
        total: 0,
        cost: 0,
      });
    }
  }, [stream.values, threadId]); // Removed onTokenUsageUpdate from dependencies to prevent infinite loop
  
  // Reset the real-time update flag when thread changes
  useEffect(() => {
    hasReceivedRealTimeUpdate.current = false;
    previousTokenUsageRef.current = null; // Reset previous usage when thread changes
  }, [threadId]);

  // Merge local state with stream.values for subagent_tool_calls_map
  // Local state has real-time updates from stream_writer, stream.values has final state
  const mergedSubagentToolCallsMap = useMemo(() => {
    const streamMap = stream.values?.subagent_tool_calls_map || {};
    const merged = {
      ...streamMap,
      ...localSubagentToolCallsMap,
    };
    return merged;
  }, [stream.values?.subagent_tool_calls_map, localSubagentToolCallsMap]);
  
  // Reset local state when thread changes
  useEffect(() => {
    setLocalSubagentToolCallsMap({});
    setLocalSubagentMessages([]);
  }, [threadId]);

  // Merge sub-agent messages with stream.messages for real-time display
  // Sub-agent messages come via stream_writer and need to be combined with main agent messages
  const mergedMessages = useMemo(() => {
    // Combine stream.messages with local sub-agent messages
    // Filter out duplicates by message ID
    const streamMessageIds = new Set(stream.messages.map(m => m.id));
    const uniqueSubagentMessages = localSubagentMessages.filter(m => m.id && !streamMessageIds.has(m.id));
    
    // Merge: stream.messages first, then sub-agent messages
    // This ensures main agent messages appear first, then sub-agent messages
    const merged = [...stream.messages, ...uniqueSubagentMessages];
    
    if (uniqueSubagentMessages.length > 0) {
      console.log("[useChat] Merged messages:", {
        streamMessagesCount: stream.messages.length,
        subagentMessagesCount: uniqueSubagentMessages.length,
        totalCount: merged.length,
      });
    }
    
    return merged;
  }, [stream.messages, localSubagentMessages]);

  return {
    messages: mergedMessages,  // Use merged messages instead of just stream.messages
    isLoading: stream.isLoading,
    sendMessage,
    stopStream,
    subagentToolCallsMap: mergedSubagentToolCallsMap,
  };
}

