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
  const [tokenUsage, setTokenUsage] = useState<{ input: number; output: number; completion: number; reasoning: number; total: number; cost?: number }>({
    input: 0,
    output: 0,
    completion: 0,
    reasoning: 0,
    total: 0,
    cost: 0,
  });
  const [availableModels, setAvailableModels] = useState<Array<{ name: string; input_price_per_million: number; output_price_per_million: number }>>([]);
  
  // Find tool calls for the selected sub-agent
  const subAgentToolCalls = React.useMemo<ToolCall[]>(() => {
    if (!selectedSubAgent) return [];
    
    // Find all tool calls that belong to this sub-agent
    // Sub-agent tool calls have parentToolCallId matching the sub-agent's id
    const toolCalls: ToolCall[] = [];
    processedMessages.forEach((messageData) => {
      if (messageData.subagentToolCalls) {
        messageData.subagentToolCalls.forEach((tc: ToolCall) => {
          if (tc.parentToolCallId === selectedSubAgent.id || 
              (tc.subagentType === selectedSubAgent.subAgentName && tc.parentToolCallId === selectedSubAgent.id)) {
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

  // Read token usage from /token_usage.json file
  React.useEffect(() => {
    const tokenUsageFile = files["/token_usage.json"];
    if (tokenUsageFile) {
      try {
        const usage = JSON.parse(tokenUsageFile);
        const newUsage = {
          input: usage.input || 0,
          output: usage.output || 0,
          completion: usage.completion || 0,
          reasoning: usage.reasoning || 0,
          total: usage.total || 0,
          cost: usage.cost || 0,
        };
        // Only update if values have changed to avoid unnecessary re-renders
        setTokenUsage((prev) => {
          if (prev.input !== newUsage.input || prev.output !== newUsage.output || 
              prev.total !== newUsage.total || prev.cost !== newUsage.cost) {
            console.log("[Page] ✓ Token usage updated from file:", newUsage);
            return newUsage;
          }
          return prev;
        });
      } catch (error) {
        console.error("[Page] Failed to parse token_usage.json:", error);
      }
    }
  }, [files]);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, []);

  // When the threadId changes, grab the thread state from the graph server
  useEffect(() => {
    const fetchThreadState = async () => {
      if (!threadId || !session?.accessToken) {
        setTodos([]);
        setFiles({});
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
          };
          setTodos(currentState.todos || []);
          
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
          onTokenUsageUpdate={React.useCallback((usage: { input: number; output: number; completion: number; reasoning: number; total: number; cost?: number }) => {
            setTokenUsage(usage);
          }, [])}
          tokenUsage={tokenUsage}
          onModelsUpdate={React.useCallback((models: Array<{ name: string; input_price_per_million: number; output_price_per_million: number }>) => {
            setAvailableModels(models);
          }, [])}
          availableModels={availableModels}
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

