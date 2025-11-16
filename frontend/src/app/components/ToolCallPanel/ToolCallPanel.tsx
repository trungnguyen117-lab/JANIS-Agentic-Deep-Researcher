"use client";

import React, { useMemo } from "react";
import { X, Terminal, CheckCircle, AlertCircle, Loader } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MarkdownContent } from "../MarkdownContent/MarkdownContent";
import type { ToolCall } from "../../types/types";
import styles from "./ToolCallPanel.module.scss";

interface ToolCallPanelProps {
  toolCall: ToolCall;
  onClose: () => void;
}

const ToolCallPanelComponent = ({ toolCall, onClose }: ToolCallPanelProps) => {
  const { name, args, result, status, subagentType } = useMemo(() => {
    const toolName = toolCall.name || "Unknown Tool";
    const toolArgs = toolCall.args || {};
    let parsedArgs = {};
    try {
      parsedArgs =
        typeof toolArgs === "string" ? JSON.parse(toolArgs) : toolArgs;
    } catch {
      parsedArgs = typeof toolArgs === "object" ? toolArgs : { raw: toolArgs };
    }
    const toolResult = toolCall.result || null;
    const toolStatus = toolCall.status || "completed";
    const subAgentType = toolCall.subagentType || null;

    return {
      name: toolName,
      args: parsedArgs,
      result: toolResult,
      status: toolStatus,
      subagentType: subAgentType,
    };
  }, [toolCall]);

  const statusIcon = useMemo(() => {
    switch (status) {
      case "completed":
        return <CheckCircle className={styles.statusCompleted} />;
      case "error":
        return <AlertCircle className={styles.statusError} />;
      case "pending":
        return <Loader className={styles.statusActive} />;
      default:
        return <Terminal className={styles.statusDefault} />;
    }
  }, [status]);

  const statusText = useMemo(() => {
    switch (status) {
      case "completed":
        return "Completed";
      case "error":
        return "Error";
      case "pending":
        return "Pending";
      default:
        return "Unknown";
    }
  }, [status]);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <Terminal className={styles.toolIcon} />
          <div>
            <h3 className={styles.title}>{name}</h3>
            {subagentType && (
              <div className={styles.subagentType}>
                <span>From: {subagentType}</span>
              </div>
            )}
            <div className={styles.status}>
              {statusIcon}
              <span>{statusText}</span>
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className={styles.closeButton}
        >
          <X size={20} />
        </Button>
      </div>

      <ScrollArea className={styles.messages}>
        <div className={styles.content}>
          {Object.keys(args).length > 0 && (
            <div className={styles.section}>
              <h4 className={styles.sectionTitle}>Arguments</h4>
              <div className={styles.sectionContent}>
                <pre className={styles.codeBlock}>
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
            </div>
          )}
          {result && (
            <div className={styles.section}>
              <h4 className={styles.sectionTitle}>Result</h4>
              <div className={styles.sectionContent}>
                {typeof result === "string" && result.length > 0 ? (
                  <MarkdownContent content={result} />
                ) : (
                  <pre className={styles.codeBlock}>
                    {typeof result === "string"
                      ? result
                      : JSON.stringify(result, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
          {!result && status === "pending" && (
            <div className={styles.section}>
              <div className={styles.sectionContent}>
                <p className={styles.pendingMessage}>
                  Tool call is in progress...
                </p>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

export const ToolCallPanel = React.memo(
  ToolCallPanelComponent,
  (prevProps, nextProps) => {
    const argsEqual =
      JSON.stringify(prevProps.toolCall.args) ===
      JSON.stringify(nextProps.toolCall.args);
    const resultEqual =
      JSON.stringify(prevProps.toolCall.result) ===
      JSON.stringify(nextProps.toolCall.result);
    return (
      argsEqual &&
      resultEqual &&
      prevProps.toolCall.status === nextProps.toolCall.status &&
      prevProps.toolCall.id === nextProps.toolCall.id &&
      prevProps.onClose === nextProps.onClose
    );
  },
);

ToolCallPanel.displayName = "ToolCallPanel";

