import { useCallback, useMemo, useEffect } from "react";
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
    total: number;
    cost: number;
  };
  available_models?: Array<{
    name: string;
    input_price_per_million: number;
    output_price_per_million: number;
  }>;
};

export function useChat(
  threadId: string | null,
  setThreadId: (
    value: string | ((old: string | null) => string | null) | null,
  ) => void,
  onTodosUpdate: (todos: TodoItem[]) => void,
  onFilesUpdate: (files: Record<string, string>) => void,
  onTokenUsageUpdate?: (usage: { input: number; output: number; completion: number; reasoning: number; total: number; cost?: number }) => void,
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

    const handleUpdateEvent = useCallback(
      (data: { [node: string]: Partial<StateType> }) => {
        // Check all nodes for token_usage - it might be in any node
        let foundTokenUsage = false;
        Object.entries(data).forEach(([nodeName, nodeData]) => {
        if (nodeData?.todos) {
          onTodosUpdate(nodeData.todos);
        }
        
        // Check for token_usage in nodeData (could be nested or direct)
        let tokenUsage = null;
        if (nodeData?.token_usage) {
          tokenUsage = nodeData.token_usage;
        } else if (nodeData && typeof nodeData === 'object') {
          // Check if token_usage is nested in the nodeData object
          tokenUsage = (nodeData as any).token_usage;
        }
        
        if (tokenUsage && onTokenUsageUpdate) {
          foundTokenUsage = true;
          onTokenUsageUpdate({
            input: tokenUsage.input || 0,
            output: tokenUsage.output || 0,
            completion: tokenUsage.completion || 0,
            reasoning: tokenUsage.reasoning || 0,
            total: tokenUsage.total || 0,
            cost: tokenUsage.cost || 0,
          });
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
              // Check for token_usage.json file and update token usage
              if (nodeData.files["/token_usage.json"]) {
                try {
                  const tokenUsageContent = normalizeFileContent(nodeData.files["/token_usage.json"]);
                  const usage = JSON.parse(tokenUsageContent);
                  if (onTokenUsageUpdate) {
                    onTokenUsageUpdate({
                      input: usage.input || 0,
                      output: usage.output || 0,
                      completion: usage.completion || 0,
                      reasoning: usage.reasoning || 0,
                      total: usage.total || 0,
                      cost: usage.cost || 0,
                    });
                  }
                } catch (error) {
                  console.error("[handleUpdateEvent] Failed to parse token_usage.json:", error);
                }
              }
              
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
      
      // Token usage will be handled by file reading or message parsing
    },
    [onTodosUpdate, onFilesUpdate, normalizeFileContent, onTokenUsageUpdate, onModelsUpdate],
  );

  const stream = useStream<StateType>({
    assistantId: agentId,
    client: createClient(accessToken || ""),
    reconnectOnMount: !!threadId, // Only reconnect if we have a threadId
    threadId: threadId ?? null,
    onUpdateEvent: handleUpdateEvent,
    onThreadId: setThreadId,
    defaultHeaders: {
      "x-auth-scheme": "langsmith",
    },
  });

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

  // Read token usage - prioritize response_metadata (updated immediately after each model call)
  useEffect(() => {
    if (!onTokenUsageUpdate) return;
    
    // Primary source: Get the latest token usage from the most recent AI message's response_metadata
    // This is updated immediately after each model call completes, so it's the most real-time
    let totalUsage = {
      input: 0,
      output: 0,
      completion: 0,
      reasoning: 0,
      total: 0,
      cost: 0,
    };
    
    // Find the most recent AI message with token_usage
    for (let i = stream.messages.length - 1; i >= 0; i--) {
      const msg = stream.messages[i];
      if (msg.type === "ai" && msg.response_metadata?.token_usage) {
        const usage = msg.response_metadata.token_usage as {
          input?: number;
          output?: number;
          completion?: number;
          reasoning?: number;
          total?: number;
          cost?: number;
        };
        // Use the latest cumulative value (don't sum, it's already cumulative)
        totalUsage = {
          input: usage.input || 0,
          output: usage.output || 0,
          completion: usage.completion || 0,
          reasoning: usage.reasoning || 0,
          total: usage.total || 0,
          cost: usage.cost || 0,
        };
        break; // Use the most recent value
      }
    }
    
    // Fallback 1: If no messages have token_usage, check stream.values.token_usage (from state)
    if (totalUsage.total === 0 && stream.values?.token_usage) {
      const usage = stream.values.token_usage;
      totalUsage = {
        input: usage.input || 0,
        output: usage.output || 0,
        completion: usage.completion || 0,
        reasoning: usage.reasoning || 0,
        total: usage.total || 0,
        cost: usage.cost || 0,
      };
    }
    
    // Fallback 2: Check token_usage.json file in stream.values.files
    if (totalUsage.total === 0) {
      const tokenUsageFile = stream.values?.files?.["/token_usage.json"];
      if (tokenUsageFile) {
        try {
          const usage = typeof tokenUsageFile === "string" 
            ? JSON.parse(tokenUsageFile) 
            : tokenUsageFile;
          totalUsage = {
            input: usage.input || 0,
            output: usage.output || 0,
            completion: usage.completion || 0,
            reasoning: usage.reasoning || 0,
            total: usage.total || 0,
            cost: usage.cost || 0,
          };
        } catch (error) {
          console.error("[useChat] Failed to parse token_usage.json:", error);
        }
      }
    }
    
    // Update token usage (always update, even if 0, to ensure UI reflects current state)
    onTokenUsageUpdate(totalUsage);
  }, [stream.values, stream.messages, onTokenUsageUpdate]);

  return {
    messages: stream.messages,
    isLoading: stream.isLoading,
    sendMessage,
    stopStream,
  };
}

