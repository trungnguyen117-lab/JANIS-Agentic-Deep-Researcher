"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useQueryState } from "nuqs";
import { ChatInterface } from "./components/ChatInterface/ChatInterface";
import { TasksFilesSidebar } from "./components/TasksFilesSidebar/TasksFilesSidebar";
import { SubAgentPanel } from "./components/SubAgentPanel/SubAgentPanel";
import { FileViewDialog } from "./components/FileViewDialog/FileViewDialog";
import { createClient } from "@/lib/client";
import { useAuthContext } from "@/providers/Auth";
import type { SubAgent, FileItem, TodoItem, PlanOutline, ToolCall } from "./types/types";
import { extractFileContent } from "./utils/fileContentUtils";
import styles from "./page.module.scss";

export default function HomePage() {
  const { session } = useAuthContext();
  const [threadId, setThreadId] = useQueryState("threadId");
  const [selectedSubAgent, setSelectedSubAgent] = useState<SubAgent | null>(
    null,
  );
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isLoadingThreadState, setIsLoadingThreadState] = useState(false);
  const sendMessageCallbackRef = React.useRef<((message: string) => void) | null>(null);
  const [processedMessages, setProcessedMessages] = useState<any[]>([]);
  const [tokenUsage, setTokenUsage] = useState<{ input: number; output: number; completion: number; reasoning: number; cache?: number; prompt?: number; total: number; cost?: number }>({
    input: 0,
    output: 0,
    completion: 0,
    reasoning: 0,
    total: 0,
    cost: 0,
  });
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; input_price_per_million: number; output_price_per_million: number }>>([]);
  
  // Find tool calls for the selected sub-agent
  // IMPORTANT: This handles multiple sub-agents with the same name correctly by using
  // the unique tool_call_id (selectedSubAgent.id) as the key. Each sub-agent invocation
  // has a unique tool_call_id, even if they have the same name (e.g., multiple parallel
  // "literature-review-agent" instances).
  const subAgentToolCalls = React.useMemo<ToolCall[]>(() => {
    if (!selectedSubAgent) return [];
    
    // Find all tool calls that belong to this sub-agent instance
    // Sub-agent tool calls have parentToolCallId matching the sub-agent's id (the unique tool_call_id)
    const toolCalls: ToolCall[] = [];
    
    processedMessages.forEach((messageData) => {
      if (messageData.subagentToolCalls && messageData.subagentToolCalls.length > 0) {
        messageData.subagentToolCalls.forEach((tc: ToolCall) => {
          // CRITICAL: Match by parentToolCallId ONLY (not by name/type)
          // This ensures we correctly handle multiple sub-agents with the same name
          // Each sub-agent invocation has a unique tool_call_id (selectedSubAgent.id)
          const matchesById = tc.parentToolCallId === selectedSubAgent.id;
          
          if (matchesById) {
            toolCalls.push(tc);
          }
        });
      }
    });
    
    return toolCalls;
  }, [selectedSubAgent, processedMessages]);

  // Extract outline from plan_outline.json file
  const outline = React.useMemo<PlanOutline | null>(() => {
    const outlineFile = Object.keys(files).find(f => 
      f === "/plan_outline.json" || 
      f === "plan_outline.json" ||
      f.endsWith("/plan_outline.json")
    );
    
    if (!outlineFile) return null;
    
    try {
      const fileContent = files[outlineFile];
      if (!fileContent) return null;
      
      const parsed = JSON.parse(fileContent) as PlanOutline;
      if (parsed.sections && Array.isArray(parsed.sections)) {
        return parsed;
      }
    } catch (error) {
      console.error("Failed to parse plan_outline.json:", error);
    }
    return null;
  }, [files]);

  // Token usage is read from stream.values.token_usage in useChat hook
  // No need to read from files

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, []);

  // When the threadId changes, grab the thread state from the graph server
  useEffect(() => {
    const fetchThreadState = async () => {
      if (!threadId || !session?.accessToken) {
        setTodos([]);
        setFiles({});
        // Token usage will be reset automatically when new thread starts (no state = zero usage)
        setIsLoadingThreadState(false);
        return;
      }
      setIsLoadingThreadState(true);
      try {
        const client = createClient(session.accessToken);
        const state = await client.threads.getState(threadId);

        if (state.values) {
          const currentState = state.values as {
            todos?: TodoItem[];
            files?: Record<string, any>;
            token_usage?: { input: number; output: number; completion: number; reasoning: number; cache?: number; prompt?: number; total: number; cost?: number };
          };
          setTodos(currentState.todos || []);
          
          // Reset token usage to thread's state (or zero if not present)
          // This ensures each thread has its own isolated token usage
          if (currentState.token_usage) {
            setTokenUsage({
              input: currentState.token_usage.input || 0,
              output: currentState.token_usage.output || 0,
              completion: currentState.token_usage.completion || 0,
              reasoning: currentState.token_usage.reasoning || 0,
              cache: currentState.token_usage.cache || 0,
              prompt: currentState.token_usage.prompt || 0,
              total: currentState.token_usage.total || 0,
              cost: currentState.token_usage.cost || 0,
            });
          } else {
            // If thread has no token_usage, reset to zero (new thread or no usage yet)
            setTokenUsage({
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
          
          // Normalize file content to ensure all values are strings
          const normalizedFiles: Record<string, string> = {};
          if (currentState.files) {
            Object.entries(currentState.files).forEach(([path, content]) => {
              // Use utility function to extract content from deepagents format
              const extracted = extractFileContent(content);
              normalizedFiles[path] = extracted;
            });
          }
          // When loading thread state, merge with existing files to preserve any files that might have been added via stream
          setFiles((prevFiles) => {
            // Merge thread state files with existing files
            // Thread state should be the source of truth, but we merge to avoid losing files during the brief moment between state load and stream updates
            const merged = { ...prevFiles, ...normalizedFiles };
            console.log("[Page] Thread state load - Previous:", Object.keys(prevFiles), "State:", Object.keys(normalizedFiles), "Merged:", Object.keys(merged));
            return merged;
          });
        } else {
          // If no state values, token usage will be zero (no usage yet for this thread)
          // Don't need to explicitly reset - it will be set by useChat hook when it reads from state
        }
      } catch (error) {
        console.error("Failed to fetch thread state:", error);
        setTodos([]);
        setFiles({});
      } finally {
        setIsLoadingThreadState(false);
      }
    };
    fetchThreadState();
  }, [threadId, session?.accessToken]);

  const handleNewThread = useCallback(() => {
    setThreadId(null);
    setSelectedSubAgent(null);
    setTodos([]);
    setFiles({});
    // Token usage will automatically be zero for new thread (no state = zero usage)
  }, [setThreadId]);

  return (
    <div className={styles.container}>
      <TasksFilesSidebar
        todos={todos}
        files={files}
        outline={outline}
        onFileClick={setSelectedFile}
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebar}
        onOutlineSave={React.useCallback((savedOutline: PlanOutline) => {
          // Save edited outline back to the file by sending a message
          if (sendMessageCallbackRef.current) {
            const outlineJson = JSON.stringify(savedOutline, null, 2);
            sendMessageCallbackRef.current(`Please update the plan outline file with this structure:\n\n\`\`\`OUTLINE\n${outlineJson}\n\`\`\`\n\nUse write_file to save this to /plan_outline.json`);
          }
        }, [])}
      />
      <div className={styles.mainContent}>
        <ChatInterface
          threadId={threadId}
          selectedSubAgent={selectedSubAgent}
          setThreadId={setThreadId}
          onSelectSubAgent={setSelectedSubAgent}
          onTodosUpdate={React.useCallback((todos: TodoItem[]) => {
            setTodos(todos);
          }, [])}
          onFilesUpdate={React.useCallback((newFiles: Record<string, string>) => {
            setFiles((prevFiles) => {
              // Merge new files with existing files to prevent losing files on partial updates
              // Only update files that have non-empty content to prevent overwriting with empty values
              const merged = { ...prevFiles };
              Object.entries(newFiles).forEach(([path, content]) => {
                // Only update if content is not empty/undefined/null
                if (content && typeof content === 'string' && content.trim().length > 0) {
                  merged[path] = content;
                } else if (content === null || content === undefined) {
                  // If explicitly set to null/undefined, remove the file
                  delete merged[path];
                }
                // If content is empty string, keep existing content (don't overwrite)
              });
              return merged;
            });
          }, [])}
          onNewThread={handleNewThread}
          isLoadingThreadState={isLoadingThreadState}
          onTokenUsageUpdate={React.useCallback((usage: { input: number; output: number; completion: number; reasoning: number; cache?: number; prompt?: number; total: number; cost?: number }) => {
            setTokenUsage(usage);
          }, [])}
          tokenUsage={tokenUsage}
          onModelsUpdate={React.useCallback((models: Array<{ name: string; input_price_per_million: number; output_price_per_million: number }>) => {
            setAvailableModels(models);
          }, [])}
          availableModels={availableModels}
          onProcessedMessagesReady={React.useCallback((processedMessages: any[]) => {
            setProcessedMessages((prev) => {
              // Only update if the messages actually changed
              const prevStr = JSON.stringify(prev);
              const newStr = JSON.stringify(processedMessages);
              if (prevStr !== newStr) {
                return processedMessages;
              }
              return prev;
            });
          }, [])}
        />
        {selectedSubAgent && (
          <SubAgentPanel
            subAgent={selectedSubAgent}
            toolCalls={subAgentToolCalls}
            onClose={() => setSelectedSubAgent(null)}
          />
        )}
      </div>
      {selectedFile && (
        <FileViewDialog
          file={selectedFile}
          onClose={() => setSelectedFile(null)}
        />
      )}
    </div>
  );
}

