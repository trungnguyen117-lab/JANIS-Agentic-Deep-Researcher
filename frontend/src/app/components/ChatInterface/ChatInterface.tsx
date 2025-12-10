"use client";

import React, {
  useState,
  useRef,
  useCallback,
  useMemo,
  useEffect,
  FormEvent,
} from "react";
import NextImage from "next/image";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Bot, LoaderCircle, SquarePen, History, X, Paperclip, Square } from "lucide-react";
import { ChatMessage } from "../ChatMessage/ChatMessage";
import { ThreadHistorySidebar } from "../ThreadHistorySidebar/ThreadHistorySidebar";
import { ModelSelector } from "../ModelSelector/ModelSelector";
import type { SubAgent, TodoItem, ToolCall } from "../../types/types";
import { useChat } from "../../hooks/useChat";
import styles from "./ChatInterface.module.scss";
import { Message } from "@langchain/langgraph-sdk";
import { extractStringFromMessageContent } from "../../utils/utils";

interface ChatInterfaceProps {
  threadId: string | null;
  selectedSubAgent: SubAgent | null;
  setThreadId: (
    value: string | ((old: string | null) => string | null) | null,
  ) => void;
  onSelectSubAgent: (subAgent: SubAgent) => void;
  onTodosUpdate: (todos: TodoItem[]) => void;
  onFilesUpdate: (files: Record<string, string>) => void;
  onNewThread: () => void;
  isLoadingThreadState: boolean;
  tokenUsage?: { input: number; output: number; completion: number; reasoning: number; cache?: number; prompt?: number; total: number; cost?: number };
  availableModels?: Array<{ name: string; input_price_per_million: number; output_price_per_million: number }>;
  onTokenUsageUpdate?: (usage: { input: number; output: number; completion: number; reasoning: number; cache?: number; prompt?: number; total: number; cost?: number }) => void;
  onModelsUpdate?: (models: Array<{ name: string; input_price_per_million: number; output_price_per_million: number }>) => void;
  onProcessedMessagesReady?: (processedMessages: any[]) => void; // Callback to pass processed messages to parent
}

export const ChatInterface = React.memo<ChatInterfaceProps>(
  ({
    threadId,
    selectedSubAgent,
    setThreadId,
    onSelectSubAgent,
    onTodosUpdate,
    onFilesUpdate,
    onNewThread,
    isLoadingThreadState,
    tokenUsage,
    availableModels,
    onTokenUsageUpdate,
    onModelsUpdate,
    onProcessedMessagesReady,
  }) => {
    const [input, setInput] = useState("");
    const [isThreadHistoryOpen, setIsThreadHistoryOpen] = useState(false);
    const [selectedModel, setSelectedModel] = useState<string>("gpt-4o");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const { messages, isLoading, sendMessage, stopStream, subagentToolCallsMap } = useChat(
      threadId,
      setThreadId,
      onTodosUpdate,
      onFilesUpdate,
      onTokenUsageUpdate,
      onModelsUpdate,
      selectedModel, // Pass selected model to useChat
    );

    // Only scroll to bottom when new messages are added, not on every render
    // This prevents the user message from being pushed down unnecessarily
    const prevMessagesLengthRef = useRef<number>(0);
    useEffect(() => {
      // Only scroll if a new message was actually added (length increased)
      // This prevents scrolling when messages are just being updated/reprocessed
      if (messages.length > prevMessagesLengthRef.current) {
        // Use a small delay to ensure DOM is updated
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }, 100);
        prevMessagesLengthRef.current = messages.length;
      } else if (messages.length !== prevMessagesLengthRef.current) {
        // Update ref even if length decreased (e.g., thread change)
        prevMessagesLengthRef.current = messages.length;
      }
    }, [messages.length]); // Only depend on length, not the entire messages array

    const handleSubmit = useCallback(
      (e: FormEvent) => {
        e.preventDefault();
        const messageText = input.trim();
        if (!messageText || isLoading) return;
        sendMessage(messageText);
        setInput("");
      },
      [input, isLoading, sendMessage],
    );

    const handleNewThread = useCallback(() => {
      // Cancel any ongoing thread when creating new thread
      if (isLoading) {
        stopStream();
      }
      setIsThreadHistoryOpen(false);
      onNewThread();
    }, [isLoading, stopStream, onNewThread]);

    const handleThreadSelect = useCallback(
      (id: string) => {
        setThreadId(id);
        setIsThreadHistoryOpen(false);
      },
      [setThreadId],
    );

    const toggleThreadHistory = useCallback(() => {
      setIsThreadHistoryOpen((prev) => !prev);
    }, []);

    const hasMessages = messages.length > 0;

    const processedMessages = useMemo(() => {
      /* 
    1. First pass: Process all AIMessages and collect all tool calls
    2. Second pass: Process ToolMessages and update status, only add from state map if tool calls don't exist
    */
      const messageMap = new Map<string, any>();
      // Global set to track all unique tool call IDs across all messages for deduplication
      const globalToolCallIds = new Set<string>();
      // Track all tool call IDs by their actual ID (not uniqueId) for final state deduplication
      const allToolCallIdsByActualId = new Set<string>();
      
      // FIRST PASS: Process all AIMessages first to collect all tool calls
      messages.forEach((message: Message) => {
        if (message.type === "ai") {
          // Check if this is a sub-agent AIMessage (marked with _subagent_source metadata)
          const additionalKwargs = message.additional_kwargs as any;
          const subagentSource = additionalKwargs?._subagent_source;
          const isSubagentMessage = !!subagentSource;
          
          const toolCallsInMessage: any[] = [];
          if (
            additionalKwargs?._subagent_tool_calls &&
            Array.isArray(additionalKwargs._subagent_tool_calls)
          ) {
            toolCallsInMessage.push(...additionalKwargs._subagent_tool_calls);
          }
          if (
            additionalKwargs?.tool_calls &&
            Array.isArray(additionalKwargs.tool_calls)
          ) {
            toolCallsInMessage.push(...additionalKwargs.tool_calls);
          } else if (message.tool_calls && Array.isArray(message.tool_calls)) {
            toolCallsInMessage.push(
              ...message.tool_calls.filter(
                (toolCall: any) => toolCall.name !== "",
              ),
            );
          } else if (Array.isArray(message.content)) {
            const toolUseBlocks = message.content.filter(
              (block: any) => block.type === "tool_use",
            );
            toolCallsInMessage.push(...toolUseBlocks);
          }
          const toolCallsWithStatus = toolCallsInMessage.map(
            (toolCall: any) => {
              const name =
                toolCall.function?.name ||
                toolCall.name ||
                toolCall.type ||
                "unknown";
              const args =
                toolCall.function?.arguments ||
                toolCall.args ||
                toolCall.input ||
                {};
              const toolCallId = toolCall.id || `tool-${Math.random()}`;
              const parentToolCallId = isSubagentMessage ? subagentSource.tool_call_id : undefined;
              // Create unique identifier for deduplication
              const uniqueId = `${toolCallId}-${parentToolCallId || 'main'}-${message.id || 'unknown'}`;
              
              return {
                id: toolCallId,
                name,
                args,
                status: "pending" as const,
                _uniqueId: uniqueId,
                _source: 'ai_message',
                _messageId: message.id,
                // Add sub-agent metadata if this is from a sub-agent
                ...(isSubagentMessage ? {
                  subagentType: subagentSource.subagent_type,
                  parentToolCallId: subagentSource.tool_call_id,
                } : {}),
              } as ToolCall;
            },
          );
          
          // If this is a sub-agent message, store tool calls as subagentToolCalls
          // Otherwise, store as regular toolCalls (main agent)
          // IMPORTANT: Each tool call from a sub-agent AIMessage has parentToolCallId set to
          // the unique tool_call_id, which allows us to correctly handle multiple sub-agents
          // with the same name (e.g., parallel "literature-review-agent" instances)
          
          // CRITICAL: Check if this message already exists in the map to prevent duplicates
          // If it exists, merge tool calls instead of replacing them
          const existingData = messageMap.get(message.id!);
          const messageData: any = {
            message,
            toolCalls: isSubagentMessage ? [] : toolCallsWithStatus, // Main agent tool calls
            subagentToolCalls: isSubagentMessage ? toolCallsWithStatus : [], // Sub-agent tool calls
          };
          
          // If message already exists, merge tool calls (deduplicate by uniqueId)
          if (existingData) {
            // Merge main agent tool calls
            if (!isSubagentMessage && toolCallsWithStatus.length > 0) {
              const existingUniqueIds = new Set(existingData.toolCalls?.map((tc: any) => tc._uniqueId) || []);
              toolCallsWithStatus.forEach((tc: any) => {
                if (!existingUniqueIds.has(tc._uniqueId) && !globalToolCallIds.has(tc._uniqueId)) {
                  existingData.toolCalls = existingData.toolCalls || [];
                  existingData.toolCalls.push(tc);
                  globalToolCallIds.add(tc._uniqueId);
                } else {
                  console.warn("[ChatInterface] Duplicate tool call detected (main agent):", {
                    uniqueId: tc._uniqueId,
                    id: tc.id,
                    name: tc.name,
                    messageId: message.id,
                  });
                }
              });
              messageData.toolCalls = existingData.toolCalls;
            }
            
            // Merge sub-agent tool calls
            if (isSubagentMessage && toolCallsWithStatus.length > 0) {
              const existingUniqueIds = new Set(existingData.subagentToolCalls?.map((tc: any) => tc._uniqueId) || []);
              toolCallsWithStatus.forEach((tc: any) => {
                if (!existingUniqueIds.has(tc._uniqueId) && !globalToolCallIds.has(tc._uniqueId)) {
                  existingData.subagentToolCalls = existingData.subagentToolCalls || [];
                  existingData.subagentToolCalls.push(tc);
                  globalToolCallIds.add(tc._uniqueId);
                } else {
                  // Update existing tool call with latest status
                  const existingIndex = existingData.subagentToolCalls.findIndex(
                    (etc: any) => etc._uniqueId === tc._uniqueId
                  );
                  if (existingIndex !== -1) {
                    // Preserve completed status - don't revert to pending
                    existingData.subagentToolCalls[existingIndex] = {
                      ...existingData.subagentToolCalls[existingIndex],
                      ...tc,
                      status: existingData.subagentToolCalls[existingIndex].status === "completed"
                        ? "completed"
                        : (tc.status || "pending"),
                    };
                  } else {
                    console.warn("[ChatInterface] Duplicate tool call detected (sub-agent):", {
                      uniqueId: tc._uniqueId,
                      id: tc.id,
                      name: tc.name,
                      parentToolCallId: tc.parentToolCallId,
                      messageId: message.id,
                    });
                  }
                }
              });
              messageData.subagentToolCalls = existingData.subagentToolCalls;
            }
          } else {
            // New message - track all tool calls
            toolCallsWithStatus.forEach((tc: any) => {
              if (globalToolCallIds.has(tc._uniqueId)) {
                console.warn("[ChatInterface] Duplicate tool call detected (new message):", {
                  uniqueId: tc._uniqueId,
                  id: tc.id,
                  name: tc.name,
                  parentToolCallId: tc.parentToolCallId,
                  messageId: message.id,
                });
              } else {
                globalToolCallIds.add(tc._uniqueId);
                // Also track by tool call ID for better deduplication
                if (tc.id) {
                  globalToolCallIds.add(`id:${tc.id}`);
                  allToolCallIdsByActualId.add(tc.id);
                }
              }
            });
          }
          
          messageMap.set(message.id!, messageData);
          
          if (isSubagentMessage) {
            console.log("[ChatInterface] Found sub-agent AIMessage:", {
              messageId: message.id,
              toolCallsCount: toolCallsWithStatus.length,
              subagentType: subagentSource.subagent_type,
              parentToolCallId: subagentSource.tool_call_id, // Unique ID for this sub-agent instance
              // This parentToolCallId is used to match tool calls to the correct sub-agent instance
            });
          }
        }
      });
      
      // SECOND PASS: Process all ToolMessages and update status, check for duplicates before adding from state map
      messages.forEach((message: Message) => {
        if (message.type === "tool") {
          const toolCallId = message.tool_call_id;
          if (!toolCallId) {
            return;
          }
          
          // Check if this ToolMessage is from a sub-agent
          const subagentSource = (message.additional_kwargs as any)?._subagent_source;
          const isSubagentToolMessage = !!subagentSource;
          
          // Check if this tool message contains sub-agent tool calls
          // Try multiple locations where the data might be stored
          let subagentToolCalls: any[] | undefined;
          let subagentType: string | undefined;
          
          // First, try additional_kwargs (primary location)
          if (message.additional_kwargs) {
            subagentToolCalls = (message.additional_kwargs as any)?.subagent_tool_calls;
            subagentType = (message.additional_kwargs as any)?.subagent_type;
          }
          
          // If not found, try checking the message object directly
          if (!subagentToolCalls && (message as any).subagent_tool_calls) {
            subagentToolCalls = (message as any).subagent_tool_calls;
            subagentType = (message as any).subagent_type;
          }
          
          // If still not found, try parsing from content if it's a JSON string
          if (!subagentToolCalls && typeof message.content === "string") {
            try {
              // Check if content contains embedded JSON with subagent data
              const contentStr = message.content;
              // Look for JSON-like structures in the content
              const jsonMatch = contentStr.match(/\{[\s\S]*"subagent_tool_calls"[\s\S]*\}/);
              if (jsonMatch) {
                const parsed = JSON.parse(jsonMatch[0]);
                if (parsed.subagent_tool_calls) {
                  subagentToolCalls = parsed.subagent_tool_calls;
                  subagentType = parsed.subagent_type;
                }
              }
            } catch (e) {
              // Ignore parsing errors
            }
          }
          
          // Process ToolMessage - update tool call status
          // If it's from a sub-agent, update sub-agent tool calls; otherwise update main agent tool calls
          if (isSubagentToolMessage) {
            // This ToolMessage is from a sub-agent - update sub-agent tool call status
            // Search ALL messageMap entries to find the sub-agent tool call that matches this tool_call_id
            // Sub-agent tool calls can be in any messageMap entry (they're stored with parentToolCallId)
            for (const [, data] of messageMap.entries()) {
              if (data.subagentToolCalls && Array.isArray(data.subagentToolCalls)) {
                const subagentToolCallIndex = data.subagentToolCalls.findIndex(
                  (tc: any) => tc.id === toolCallId,
                );
                if (subagentToolCallIndex !== -1) {
                  // Update the sub-agent tool call with result
                  data.subagentToolCalls[subagentToolCallIndex] = {
                    ...data.subagentToolCalls[subagentToolCallIndex],
                    status: "completed" as const,
                    result: extractStringFromMessageContent(message),
                  };
                  return; // Found and updated, exit early
                }
              }
            }
          } else {
            // This ToolMessage is from the main agent - update main agent tool call status
            for (const [, data] of messageMap.entries()) {
              // This ToolMessage is from the main agent - update main agent tool call status
              const toolCallIndex = data.toolCalls.findIndex(
                (tc: any) => tc.id === toolCallId,
              );
              if (toolCallIndex !== -1) {
                // Update the tool call with result
                data.toolCalls[toolCallIndex] = {
                  ...data.toolCalls[toolCallIndex],
                  status: "completed" as const,
                  result: extractStringFromMessageContent(message),
                };
                
                // CRITICAL: Check if sub-agent tool calls already exist in ANY messageMap entry
                // Tool calls should be added from AIMessages, not from ToolMessages/state map
                // This prevents duplicates - we only add from state map if they don't exist anywhere
                // Check by both parentToolCallId AND by individual tool call IDs
                let toolCallsExistAnywhere = false;
                const existingUniqueIds: string[] = [];
                const existingToolCallIds: string[] = [];
                
                // First, check if we have tool calls from state map
                const stateData = subagentToolCallsMap?.[toolCallId];
                const stateToolCalls = stateData?.tool_calls || [];
                
                // CRITICAL: Check if ANY of the state tool calls already exist by their actual ID
                // This is the most reliable check - if the same tool call ID exists, it's a duplicate
                for (const stateTc of stateToolCalls) {
                  const stateTcId = stateTc.id;
                  if (stateTcId && (allToolCallIdsByActualId.has(stateTcId) || globalToolCallIds.has(`id:${stateTcId}`))) {
                    toolCallsExistAnywhere = true;
                    console.log("[ChatInterface] Found existing tool call by ID (preventing duplicate from final state):", {
                      toolCallId,
                      stateTcId,
                      name: stateTc.name,
                      inAllToolCallIds: allToolCallIdsByActualId.has(stateTcId),
                      inGlobalSet: globalToolCallIds.has(`id:${stateTcId}`),
                    });
                    break;
                  }
                }
                
                // Also check messageMap entries by parentToolCallId
                if (!toolCallsExistAnywhere) {
                  for (const [, otherData] of messageMap.entries()) {
                    if (otherData.subagentToolCalls && Array.isArray(otherData.subagentToolCalls)) {
                      // Check if any tool call has this parentToolCallId
                      const toolCallsForThisSubAgent = otherData.subagentToolCalls.filter(
                        (tc: any) => tc.parentToolCallId === toolCallId
                      );
                      if (toolCallsForThisSubAgent.length > 0) {
                        toolCallsExistAnywhere = true;
                        toolCallsForThisSubAgent.forEach((tc: any) => {
                          if (tc._uniqueId) existingUniqueIds.push(tc._uniqueId);
                          if (tc.id) {
                            existingToolCallIds.push(tc.id);
                            globalToolCallIds.add(`id:${tc.id}`); // Track by ID
                            allToolCallIdsByActualId.add(tc.id); // Track in actual ID set
                          }
                          globalToolCallIds.add(tc._uniqueId); // Ensure they're in global set
                        });
                        break;
                      }
                    }
                  }
                }
                
                if (toolCallsExistAnywhere) {
                  console.log("[ChatInterface] Tool calls already exist from AIMessage, skipping state map:", {
                    toolCallId,
                    existingUniqueIds,
                    existingToolCallIds,
                    count: existingUniqueIds.length,
                  });
                }
                
                // Only add tool calls from state map if they don't already exist
                // This prevents duplicates when ToolMessages arrive after AIMessages or when final state is returned
                if (!toolCallsExistAnywhere) {
                  // If subagentToolCalls not found in message, try reading from state
                  // CRITICAL: For parallel sub-agents, toolCallId here is the parent task tool call ID
                  // This uniquely identifies which sub-agent instance these tool calls belong to
                  // Each parallel sub-agent has a unique tool_call_id, so toolCallId correctly isolates them
                  if (!subagentToolCalls || !Array.isArray(subagentToolCalls) || subagentToolCalls.length === 0) {
                    // Fallback: read from state map
                    // The key (toolCallId) is the unique identifier for this sub-agent instance
                    // This ensures parallel sub-agents don't mix their tool calls
                    const stateData = subagentToolCallsMap?.[toolCallId];
                    if (stateData && stateData.tool_calls && Array.isArray(stateData.tool_calls)) {
                      subagentToolCalls = stateData.tool_calls;
                      subagentType = stateData.subagent_type || subagentType;
                    }
                  }
                  
                  // CRITICAL: Only add tool calls if they match the expected subagent type
                  // This prevents tool calls from other sub-agents from being incorrectly associated
                  // For parallel sub-agents, this ensures each sub-agent only gets its own tool calls
                  if (subagentToolCalls && Array.isArray(subagentToolCalls) && subagentToolCalls.length > 0) {
                    // Verify that the subagentType matches (if available)
                    const stateData = subagentToolCallsMap?.[toolCallId];
                    const expectedSubagentType = stateData?.subagent_type || subagentType;
                    
                    // CRITICAL: For parallel sub-agents, verify type match to prevent cross-contamination
                    // Each sub-agent instance has a unique tool_call_id, but we also verify type as a safety check
                    if (!subagentType || !expectedSubagentType || subagentType === expectedSubagentType) {
                      // Initialize sub-agent tool calls array if it doesn't exist
                      if (!data.subagentToolCalls) {
                        data.subagentToolCalls = [];
                      }
                      
                      // Add sub-agent tool calls with metadata and unique identifier
                      // parentToolCallId is the unique tool_call_id for this sub-agent instance
                      // This allows the frontend to correctly filter tool calls for parallel sub-agents
                      subagentToolCalls.forEach((tc: any) => {
                        const tcId = tc.id || `tool-${Math.random()}`;
                        const uniqueId = `${tcId}-${toolCallId}-${message.id || 'tool-msg'}`;
                        
                        // CRITICAL: Check for duplicates using BOTH uniqueId AND tool call ID
                        // This prevents duplicates when final state is returned with all tool calls
                        // Check by actual ID first (most reliable) since same IDs mean same tool calls
                        const isDuplicateById = tcId && (allToolCallIdsByActualId.has(tcId) || globalToolCallIds.has(`id:${tcId}`));
                        const isDuplicateByUniqueId = globalToolCallIds.has(uniqueId);
                        const isDuplicate = isDuplicateById || isDuplicateByUniqueId || existingToolCallIds.includes(tcId);
                        
                        if (isDuplicate) {
                          console.warn("[ChatInterface] Duplicate tool call from state map (final state), skipping:", {
                            uniqueId,
                            id: tcId,
                            name: tc.name,
                            parentToolCallId: toolCallId,
                            messageId: message.id,
                            isDuplicateById,
                            isDuplicateByUniqueId,
                            inAllToolCallIds: allToolCallIdsByActualId.has(tcId),
                            inGlobalSet: globalToolCallIds.has(`id:${tcId}`),
                            inExistingIds: existingToolCallIds.includes(tcId),
                          });
                          return; // Skip duplicate
                        }
                        
                        data.subagentToolCalls!.push({
                          ...tc,
                          id: tcId,
                          _uniqueId: uniqueId,
                          _source: 'state_map',
                          _messageId: message.id,
                          subagentType: expectedSubagentType || subagentType,
                          parentToolCallId: toolCallId, // Unique ID for this sub-agent instance (critical for parallel execution)
                        });
                        globalToolCallIds.add(uniqueId);
                        if (tcId) {
                          globalToolCallIds.add(`id:${tcId}`); // Track by ID for better deduplication
                          allToolCallIdsByActualId.add(tcId); // Track in actual ID set
                        }
                        existingToolCallIds.push(tcId); // Track by ID too
                      });
                    } else {
                      console.warn("[ChatInterface] Sub-agent type mismatch (parallel sub-agents protection):", {
                        toolCallId,
                        messageSubagentType: subagentType,
                        stateSubagentType: expectedSubagentType,
                        toolCallsCount: subagentToolCalls.length,
                      });
                    }
                  }
                } else {
                  // Tool calls already exist from AIMessage - don't add duplicates from state map
                  console.log("[ChatInterface] Skipping duplicate tool calls from state map - already exist from AIMessage:", {
                    toolCallId,
                    existingCount: Array.from(messageMap.values()).reduce(
                      (sum, d) => sum + (d.subagentToolCalls?.filter((tc: any) => tc.parentToolCallId === toolCallId).length || 0),
                      0
                    ),
                  });
                }
                
                break; // Found and updated, exit loop
              }
            }
          }
        }
      });
      
      // THIRD PASS: Process human messages (if any weren't processed)
      messages.forEach((message: Message) => {
        if (message.type === "human" && !messageMap.has(message.id!)) {
          messageMap.set(message.id!, {
            message,
            toolCalls: [],
          });
        }
      });
      
      // CRITICAL: Preserve original message order by processing messages in their original sequence
      // Map doesn't guarantee order, so we need to reconstruct the array in the original message order
      const processedArray: any[] = [];
      const processedMessageIds = new Set<string>();
      
      // Process messages in their original order to maintain chronological sequence
      messages.forEach((message: Message) => {
        const messageData = messageMap.get(message.id!);
        if (messageData && !processedMessageIds.has(message.id!)) {
          processedArray.push(messageData);
          processedMessageIds.add(message.id!);
        }
      });
      
      // Also include any messages in the map that weren't in the original messages array
      // (this shouldn't happen, but just in case)
      messageMap.forEach((data, messageId) => {
        if (!processedMessageIds.has(messageId)) {
          processedArray.push(data);
        }
      });
      
      return processedArray.map((data, index) => {
        const prevMessage =
          index > 0 ? processedArray[index - 1].message : null;
        return {
          ...data,
          showAvatar: data.message.type !== prevMessage?.type,
        };
      });
    }, [messages, subagentToolCallsMap]);

    // Pass processed messages to parent component
    // Use a ref to track the last sent messages to prevent infinite loops
    const lastSentMessagesRef = useRef<any[]>([]);
    useEffect(() => {
      if (onProcessedMessagesReady) {
        // Only update if processedMessages actually changed
        const currentMessagesStr = JSON.stringify(processedMessages);
        const lastSentStr = JSON.stringify(lastSentMessagesRef.current);
        if (currentMessagesStr !== lastSentStr) {
          lastSentMessagesRef.current = processedMessages;
          onProcessedMessagesReady(processedMessages);
        }
      }
    }, [processedMessages, onProcessedMessagesReady]);

    return (
      <div className={styles.container}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <NextImage src="/hello.png" alt="Janis Logo" width={24} height={24} className={styles.logo} />
            <h1 className={styles.title}>Janis</h1>
          </div>
          <div className={styles.headerRight}>
            <ModelSelector
              tokenUsage={tokenUsage}
              availableModels={availableModels}
              onModelChange={setSelectedModel}
              disabled={messages.length > 0} // Disable after first message
            />
            <Button
              variant="ghost"
              size="icon"
              onClick={handleNewThread}
              disabled={!hasMessages}
            >
              <SquarePen size={20} />
            </Button>
            <Button variant="ghost" size="icon" onClick={toggleThreadHistory}>
              <History size={20} />
            </Button>
          </div>
        </div>
        <div className={styles.content}>
          <ThreadHistorySidebar
            open={isThreadHistoryOpen}
            setOpen={setIsThreadHistoryOpen}
            currentThreadId={threadId}
            onThreadSelect={handleThreadSelect}
          />
          <div className={styles.messagesContainer}>
            {!hasMessages && !isLoading && !isLoadingThreadState && (
              <div className={styles.emptyState}>
                <NextImage src="/hello.png" alt="Janis Logo" width={64} height={64} className={styles.emptyIcon} />
                <h2>Start a conversation or select a thread from history</h2>
              </div>
            )}
            {isLoadingThreadState && (
              <div className={styles.threadLoadingState}>
                <LoaderCircle className={styles.threadLoadingSpinner} />
              </div>
            )}
            <div className={styles.messagesList}>
              {processedMessages
                .filter((data) => {
                  // Filter out sub-agent AIMessages from main chat view
                  // They're included in message history for tool call preservation,
                  // but shouldn't be displayed in the main chat
                  if (data.message.type === "ai") {
                    const subagentSource = (data.message.additional_kwargs as any)?._subagent_source;
                    if (subagentSource) {
                      return false; // Hide sub-agent AIMessages from main chat
                    }
                  }
                  return true;
                })
                .map((data) => (
                  <ChatMessage
                    key={data.message.id}
                    message={data.message}
                    toolCalls={data.toolCalls}
                    subagentToolCalls={data.subagentToolCalls || []}
                    showAvatar={data.showAvatar}
                    onSelectSubAgent={onSelectSubAgent}
                    selectedSubAgent={selectedSubAgent}
                    onApprove={
                      data.message.type === "ai"
                        ? () => sendMessage("approve")
                        : undefined
                    }
                  />
                ))}
              {isLoading && (
                <div className={styles.loadingMessage}>
                  <LoaderCircle className={styles.spinner} />
                  <span>Working...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className={styles.inputForm}>
          <div className={styles.inputRow}>

            <input
              type="file"
              id="file-upload"
              className="hidden"
              onChange={(e) => {
                // Placeholder for file upload logic
                console.log("File selected:", e.target.files?.[0]);
              }}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={styles.attachButton}
              onClick={() => document.getElementById("file-upload")?.click()}
              disabled={isLoading}
            >
              <Paperclip size={20} />
            </Button>
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // Auto-resize
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e as any);
                }
              }}
              placeholder="Type your message..."
              disabled={isLoading}
              className={styles.input}
              rows={1}
            />
            {isLoading ? (
              <Button
                type="button"
                onClick={stopStream}
                className={styles.stopButton}
                title="Stop generating"
              >
                <Square size={16} fill="currentColor" />
              </Button>
            ) : (
              <Button
                type="submit"
                disabled={!input.trim()}
                className={styles.sendButton}
              >
                <Send size={16} />
              </Button>
            )}
          </div>
        </form>
      </div>
    );
  },
);

ChatInterface.displayName = "ChatInterface";
