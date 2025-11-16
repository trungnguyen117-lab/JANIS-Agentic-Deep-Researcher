"use client";

import React, {
  useState,
  useRef,
  useCallback,
  useMemo,
  useEffect,
  FormEvent,
} from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Bot, LoaderCircle, SquarePen, History, X } from "lucide-react";
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

    const { messages, isLoading, sendMessage, stopStream, subagentToolCallsMap } = useChat(
      threadId,
      setThreadId,
      onTodosUpdate,
      onFilesUpdate,
      onTokenUsageUpdate,
      onModelsUpdate,
      selectedModel, // Pass selected model to useChat
    );

    useEffect(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

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
    1. Loop through all messages
    2. For each AI message, add the AI message, and any tool calls to the messageMap
    3. For each tool message, find the corresponding tool call in the messageMap and update the status and output
    */
      const messageMap = new Map<string, any>();
      messages.forEach((message: Message) => {
        if (message.type === "ai") {
          // Check if this is a sub-agent AIMessage (marked with _subagent_source metadata)
          const subagentSource = (message.additional_kwargs as any)?._subagent_source;
          const isSubagentMessage = !!subagentSource;
          
          const toolCallsInMessage: any[] = [];
          if (
            message.additional_kwargs?.tool_calls &&
            Array.isArray(message.additional_kwargs.tool_calls)
          ) {
            toolCallsInMessage.push(...message.additional_kwargs.tool_calls);
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
              return {
                id: toolCall.id || `tool-${Math.random()}`,
                name,
                args,
                status: "pending" as const,
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
          const messageData: any = {
            message,
            toolCalls: isSubagentMessage ? [] : toolCallsWithStatus, // Main agent tool calls
            subagentToolCalls: isSubagentMessage ? toolCallsWithStatus : [], // Sub-agent tool calls
          };
          
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
        } else if (message.type === "tool") {
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
                
                // If subagentToolCalls not found in message, try reading from state
                if (!subagentToolCalls || !Array.isArray(subagentToolCalls) || subagentToolCalls.length === 0) {
                  // Fallback: read from state map
                  const stateData = subagentToolCallsMap?.[toolCallId];
                  if (stateData && stateData.tool_calls && Array.isArray(stateData.tool_calls)) {
                    subagentToolCalls = stateData.tool_calls;
                    subagentType = stateData.subagent_type || subagentType;
                  }
                }
                
                // If this is a task tool call with sub-agent tool calls, add them to the message
                if (subagentToolCalls && Array.isArray(subagentToolCalls) && subagentToolCalls.length > 0) {
                  // Add sub-agent tool calls to the message data
                  if (!data.subagentToolCalls) {
                    data.subagentToolCalls = [];
                  }
                  // Add sub-agent tool calls with metadata
                  subagentToolCalls.forEach((tc: any) => {
                    data.subagentToolCalls!.push({
                      ...tc,
                      subagentType: subagentType,
                      parentToolCallId: toolCallId,
                    });
                  });
                }
                
                break; // Found and updated, exit loop
              }
            }
          }
        } else if (message.type === "human") {
          messageMap.set(message.id!, {
            message,
            toolCalls: [],
          });
        }
      });
      const processedArray = Array.from(messageMap.values());
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
            <Bot className={styles.logo} />
            <h1 className={styles.title}>Deep Agents</h1>
          </div>
          <div className={styles.headerRight}>
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
                <Bot size={48} className={styles.emptyIcon} />
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
            <ModelSelector
              tokenUsage={tokenUsage}
              availableModels={availableModels}
              onModelChange={setSelectedModel}
              disabled={messages.length > 0} // Disable after first message
            />
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              disabled={isLoading}
              className={styles.input}
            />
            {isLoading ? (
              <Button
                type="button"
                onClick={stopStream}
                className={styles.stopButton}
              >
                Stop
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
