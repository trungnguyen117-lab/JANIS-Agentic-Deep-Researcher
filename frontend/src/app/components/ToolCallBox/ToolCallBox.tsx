"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  Terminal,
  CheckCircle,
  AlertCircle,
  Loader,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import styles from "./ToolCallBox.module.scss";
import { ToolCall } from "../../types/types";

interface ToolCallBoxProps {
  toolCall: ToolCall;
}

export const ToolCallBox = React.memo<ToolCallBoxProps>(({ toolCall }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const { name, args, result, status, uniqueId, source } = useMemo(() => {
    const toolName = toolCall.name || "Unknown Tool";
    const toolArgs = toolCall.args || "{}";
    let parsedArgs = {};
    try {
      parsedArgs =
        typeof toolArgs === "string" ? JSON.parse(toolArgs) : toolArgs;
    } catch {
      parsedArgs = { raw: toolArgs };
    }
    const toolResult = toolCall.result || null;
    const toolStatus = toolCall.status || "completed";
    const uniqueId = toolCall._uniqueId || toolCall.id || "unknown";
    const source = toolCall._source || "unknown";

    // Debug logging to verify uniqueId is set
    if (!toolCall._uniqueId) {
      console.warn("[ToolCallBox] Missing _uniqueId for tool call:", {
        id: toolCall.id,
        name: toolName,
        hasUniqueId: !!toolCall._uniqueId,
        hasSource: !!toolCall._source,
        hasMessageId: !!toolCall._messageId,
        toolCall: toolCall,
      });
    }

    return {
      name: toolName,
      args: parsedArgs,
      result: toolResult,
      status: toolStatus,
      uniqueId,
      source,
    };
  }, [toolCall]);

  const statusIcon = useMemo(() => {
    switch (status) {
      case "completed":
        return <CheckCircle className={styles.statusCompleted} />;
      case "error":
        return <AlertCircle className={styles.statusError} />;
      case "pending":
        return <Loader className={styles.statusRunning} />;
      default:
        return <Terminal className={styles.statusDefault} />;
    }
  }, [status]);

  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const hasContent = result || Object.keys(args).length > 0;

  return (
    <div className={styles.container}>
      <Button
        variant="ghost"
        size="sm"
        onClick={toggleExpanded}
        className={styles.header}
        disabled={!hasContent}
      >
        <div className={styles.headerLeft}>
          {hasContent && isExpanded ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronRight size={14} />
          )}
          {statusIcon}
          <span className={styles.toolName}>{name}</span>
          <span 
            className={styles.uniqueId} 
            title={`Unique ID: ${uniqueId}\nSource: ${source}\nID: ${toolCall.id}\nMessage ID: ${toolCall._messageId || 'N/A'}\nParent: ${toolCall.parentToolCallId || 'N/A'}`}
          >
            {uniqueId && uniqueId !== 'unknown' 
              ? `[${uniqueId.includes('-') ? uniqueId.split('-')[0] : uniqueId.substring(0, 8)}]`
              : `[${toolCall.id?.substring(0, 8) || 'no-id'}]`
            }
          </span>
        </div>
      </Button>

      {isExpanded && hasContent && (
        <div className={styles.content}>
          {Object.keys(args).length > 0 && (
            <div className={styles.section}>
              <h4 className={styles.sectionTitle}>Arguments</h4>
              <pre className={styles.codeBlock}>
                {JSON.stringify(args, null, 2)}
              </pre>
            </div>
          )}
          {result && (
            <div className={styles.section}>
              <h4 className={styles.sectionTitle}>Result</h4>
              <pre className={styles.codeBlock}>
                {typeof result === "string"
                  ? result
                  : JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

ToolCallBox.displayName = "ToolCallBox";
