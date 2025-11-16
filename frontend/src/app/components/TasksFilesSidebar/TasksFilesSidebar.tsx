"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Folder,
  FolderOpen,
  CheckCircle,
  Circle,
  Clock,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { PlanOutline as PlanOutlineComponent } from "../PlanOutline/PlanOutline";
import type { TodoItem, FileItem, PlanOutline } from "../../types/types";
import { extractFileContent } from "../../utils/fileContentUtils";
import styles from "./TasksFilesSidebar.module.scss";

interface TasksFilesSidebarProps {
  todos: TodoItem[];
  files: Record<string, string>;
  outline?: PlanOutline | null;
  onFileClick: (file: FileItem) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onOutlineSave?: (outline: PlanOutline) => void;
}

export const TasksFilesSidebar = React.memo<TasksFilesSidebarProps>(
  ({ todos, files, outline, onFileClick, collapsed, onToggleCollapse, onOutlineSave }) => {
    // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
    // This ensures hooks are always called in the same order
    
    // Debug logging
    React.useEffect(() => {
      console.log("[TasksFilesSidebar] Outline prop:", outline);
      console.log("[TasksFilesSidebar] Outline sections:", outline?.sections?.length);
      console.log("[TasksFilesSidebar] Files available:", Object.keys(files));
    }, [outline, files]);
    
    const getStatusIcon = useCallback((status: TodoItem["status"]) => {
      switch (status) {
        case "completed":
          return <CheckCircle size={16} className={styles.completedIcon} />;
        case "in_progress":
          return <Clock size={16} className={styles.progressIcon} />;
        default:
          return <Circle size={16} className={styles.pendingIcon} />;
      }
    }, []);

    const groupedTodos = useMemo(() => {
      return {
        pending: todos.filter((t) => t.status === "pending"),
        in_progress: todos.filter((t) => t.status === "in_progress"),
        completed: todos.filter((t) => t.status === "completed"),
      };
    }, [todos]);

    // Memoize callbacks for outline component - must be at top level (Rules of Hooks)
    const handleOutlineChange = useCallback(() => {
      // Update is handled internally by PlanOutline component
      // No need to propagate changes until save
    }, []);

    const handleOutlineSave = useCallback((savedOutline: PlanOutline) => {
      if (onOutlineSave) {
        onOutlineSave(savedOutline);
      }
    }, [onOutlineSave]);

    // Early return AFTER all hooks are called
    if (collapsed) {
      return (
        <div className={styles.sidebarCollapsed}>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className={styles.toggleButton}
          >
            <ChevronRight size={20} />
          </Button>
        </div>
      );
    }

    return (
      <div className={styles.sidebar}>
        <div className={styles.header}>
          <h2 className={styles.title}>Workspace</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className={styles.toggleButton}
          >
            <ChevronLeft size={20} />
          </Button>
        </div>
        <Tabs defaultValue="tasks" className={styles.tabs}>
          <TabsList className={styles.tabsList}>
            <TabsTrigger value="tasks" className={styles.tabTrigger}>
              Tasks ({todos.length})
            </TabsTrigger>
            <TabsTrigger value="files" className={styles.tabTrigger}>
              Files ({Object.keys(files).length})
            </TabsTrigger>
            <TabsTrigger value="outline" className={styles.tabTrigger}>
              Outline {outline && outline.sections ? `(${outline.sections.length})` : ''}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="tasks" className={styles.tabContent}>
            <ScrollArea className={styles.scrollArea}>
              {todos.length === 0 ? (
                <div className={styles.emptyState}>
                  <p>No tasks yet</p>
                </div>
              ) : (
                <div className={styles.todoGroups}>
                  {groupedTodos.in_progress.length > 0 && (
                    <div className={styles.todoGroup}>
                      <h3 className={styles.groupTitle}>In Progress</h3>
                      {groupedTodos.in_progress.map((todo, index) => (
                        <div key={`in_progress_${todo.id}_${index}`} className={styles.todoItem}>
                          {getStatusIcon(todo.status)}
                          <span className={styles.todoContent}>
                            {todo.content}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {groupedTodos.pending.length > 0 && (
                    <div className={styles.todoGroup}>
                      <h3 className={styles.groupTitle}>Pending</h3>
                      {groupedTodos.pending.map((todo, index) => (
                        <div key={`pending_${todo.id}_${index}`} className={styles.todoItem}>
                          {getStatusIcon(todo.status)}
                          <span className={styles.todoContent}>
                            {todo.content}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {groupedTodos.completed.length > 0 && (
                    <div className={styles.todoGroup}>
                      <h3 className={styles.groupTitle}>Completed</h3>
                      {groupedTodos.completed.map((todo, index) => (
                        <div key={`completed_${todo.id}_${index}`} className={styles.todoItem}>
                          {getStatusIcon(todo.status)}
                          <span className={styles.todoContent}>
                            {todo.content}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          <TabsContent value="files" className={styles.tabContent}>
            <ScrollArea className={styles.scrollArea}>
              {Object.keys(files).length === 0 ? (
                <div className={styles.emptyState}>
                  <p>No files yet</p>
                </div>
              ) : (
                <div className={styles.fileTree}>
                  {Object.keys(files).map((file) => {
                    // Use utility function to extract content from deepagents format
                    const fileContent = extractFileContent(files[file]);
                    return (
                      <div key={file} className={styles.fileItem}>
                        <div
                          className={styles.fileRow}
                          onClick={() =>
                            onFileClick({ path: file, content: fileContent })
                          }
                        >
                          <FileText size={16} />
                          <span className={styles.fileName}>{file}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          <TabsContent value="outline" className={styles.tabContent}>
            {outline && outline.sections && outline.sections.length > 0 ? (
              <ScrollArea className={styles.scrollArea}>
                <div className={styles.outlineWrapper}>
                  <PlanOutlineComponent
                    outline={outline}
                    editable={true}
                    onOutlineChange={handleOutlineChange}
                    onSave={handleOutlineSave}
                  />
                </div>
              </ScrollArea>
            ) : (
              <ScrollArea className={styles.scrollArea}>
                <div className={styles.emptyState}>
                  <p>No outline yet</p>
                  {outline && (
                    <p style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
                      Debug: Outline exists but has {outline.sections?.length || 0} sections
                    </p>
                  )}
                </div>
              </ScrollArea>
            )}
          </TabsContent>
        </Tabs>
      </div>
    );
  },
);

TasksFilesSidebar.displayName = "TasksFilesSidebar";
