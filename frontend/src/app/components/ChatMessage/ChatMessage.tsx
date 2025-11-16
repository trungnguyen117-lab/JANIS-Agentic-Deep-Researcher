"use client";

import React, { useEffect, useMemo, useRef } from "react";
import { User, Bot, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubAgentIndicator } from "../SubAgentIndicator/SubAgentIndicator";
import { MarkdownContent } from "../MarkdownContent/MarkdownContent";
import { ToolCallBox } from "../ToolCallBox/ToolCallBox";
import type { SubAgent, ToolCall } from "../../types/types";
import styles from "./ChatMessage.module.scss";
import { Message } from "@langchain/langgraph-sdk";
import { extractStringFromMessageContent } from "../../utils/utils";

interface ChatMessageProps {
  message: Message;
  toolCalls: ToolCall[];
  subagentToolCalls?: ToolCall[]; // Tool calls from sub-agents
  showAvatar: boolean;
  onSelectSubAgent: (subAgent: SubAgent) => void;
  selectedSubAgent: SubAgent | null;
  onApprove?: () => void;
  sendMessage?: (message: string) => void;
  hasOutlineFile?: boolean; // Whether plan_outline.json exists
}

export const ChatMessage = React.memo<ChatMessageProps>(
  ({ message, toolCalls, subagentToolCalls = [], showAvatar, onSelectSubAgent, selectedSubAgent, onApprove, sendMessage, hasOutlineFile = false }) => {
    const isUser = message.type === "human";
    const messageContent = extractStringFromMessageContent(message);
    const hasContent = messageContent && messageContent.trim() !== "";
    const hasToolCalls = toolCalls.length > 0;
    
    // Extract sub-agents from tool calls
    const subAgents = useMemo(() => {
      const filtered = toolCalls
        .filter((toolCall: ToolCall) => {
          const isTask = toolCall.name === "task";
          const hasSubagentType = toolCall.args && (
            toolCall.args["subagent_type"] ||
            toolCall.args["subagentType"] ||
            toolCall.args.subagent_type
          );
          
          return isTask && hasSubagentType;
        })
        .map((toolCall: ToolCall) => {
          const subagentType = 
            toolCall.args["subagent_type"] || 
            toolCall.args["subagentType"] ||
            toolCall.args.subagent_type;
          
          return {
            id: toolCall.id,
            name: toolCall.name,
            subAgentName: subagentType,
            input: toolCall.args["description"] || toolCall.args.description,
            output: toolCall.result,
            status: toolCall.status,
          };
        });
      
      return filtered;
    }, [toolCalls, message.id]);

    // Detect if this message is from the planning-agent and the plan is ready for approval
    const isPlanProposal = useMemo(() => {
      // Don't show for user messages
      if (isUser) {
        return false;
      }
      
      // Check if any sub-agent in this message is the planning-agent
      const planningAgentSubAgents = subAgents.filter(
        (subAgent: SubAgent) => subAgent.subAgentName === "planning-agent"
      );
      
      // Also check if outline file exists (more reliable indicator)
      const hasPlanningAgent = planningAgentSubAgents.length > 0;
      const hasOutline = hasOutlineFile;
      
      // Show approve button if:
      // 1. There's a planning-agent sub-agent (task was delegated), AND
      // 2. Either the outline file exists OR at least one planning-agent task has completed with output
      // Note: We don't require messageContent because the message might only have tool calls initially
      if (!hasPlanningAgent) {
        return false;
      }
      
      // If outline file exists, that's a strong indicator the plan is ready
      if (hasOutline) {
        return true;
      }
      
      // Otherwise, check if planning-agent task has completed
      const hasCompletedPlanningAgent = planningAgentSubAgents.some(
        (subAgent: SubAgent) => {
          const hasOutput = subAgent.output !== undefined &&
                           subAgent.output !== null &&
                           subAgent.output !== "";
          const isCompleted = subAgent.status === "completed" || 
                             (subAgent.status !== "pending" && hasOutput);
          
          return isCompleted && hasOutput;
        }
      );
      
      return hasCompletedPlanningAgent;
    }, [isUser, messageContent, subAgents, hasOutlineFile, message.id]);

    const subAgentsString = useMemo(() => {
      return JSON.stringify(subAgents);
    }, [subAgents]);

    // Filter orchestrator tool calls (non-task tool calls)
    // These are tool calls made by the orchestrator itself, not delegated to sub-agents
    const orchestratorToolCalls = useMemo(() => {
      const filtered = toolCalls.filter((toolCall: ToolCall) => {
        // Exclude "task" tool calls (these are sub-agent delegations)
        const isTaskCall = toolCall.name === "task";
        return !isTaskCall;
      });
      
      return filtered;
    }, [toolCalls, message.id, isUser]);

    // Sync selectedSubAgent with subAgents array if it exists
    // This ensures that if subAgents array updates (e.g., tool calls complete), 
    // the selectedSubAgent object is updated with the latest data
    // We use refs to track state and prevent infinite loops
    const lastSyncedSubAgentsStringRef = useRef<string | null>(null);
    const selectedSubAgentRef = useRef(selectedSubAgent);
    const onSelectSubAgentRef = useRef(onSelectSubAgent);
    
    // Keep refs up to date
    useEffect(() => {
      selectedSubAgentRef.current = selectedSubAgent;
      onSelectSubAgentRef.current = onSelectSubAgent;
    }, [selectedSubAgent, onSelectSubAgent]);
    
    useEffect(() => {
      // Only sync if subAgents have actually changed (not just selectedSubAgent)
      if (lastSyncedSubAgentsStringRef.current === subAgentsString) {
        return; // Sub-agents haven't changed, no need to sync
      }
      
      // Update the ref to mark that we've processed this subAgentsString
      lastSyncedSubAgentsStringRef.current = subAgentsString;
      
      // Only sync if we have a selectedSubAgent (use ref to avoid dependency)
      const currentSelectedSubAgent = selectedSubAgentRef.current;
      if (!currentSelectedSubAgent) {
        return;
      }
      
      // Check if selectedSubAgent exists in subAgents
      const foundSubAgent = subAgents.find(
        (subAgent: SubAgent) => subAgent.id === currentSelectedSubAgent.id,
      );
      
      // Only update if we found a match AND the object reference is different (data has changed)
      if (foundSubAgent && foundSubAgent !== currentSelectedSubAgent) {
        // Use requestAnimationFrame to defer the update and break any synchronous loops
        requestAnimationFrame(() => {
          onSelectSubAgentRef.current(foundSubAgent);
        });
      }
    }, [subAgentsString, subAgents]); // ONLY depend on subAgentsString and subAgents - this prevents loops when selectedSubAgent changes

    return (
      <div
        className={`${styles.message} ${isUser ? styles.user : styles.assistant}`}
      >
        <div
          className={`${styles.avatar} ${!showAvatar ? styles.avatarHidden : ""}`}
        >
          {showAvatar &&
            (isUser ? (
              <User className={styles.avatarIcon} />
            ) : (
              <Bot className={styles.avatarIcon} />
            ))}
        </div>
        <div className={styles.content}>
          {hasContent && (
            <div className={styles.bubble}>
              {isUser ? (
                <p className={styles.text}>{messageContent}</p>
              ) : (
                <>
                  <MarkdownContent content={messageContent} />
                  {isPlanProposal && onApprove && (
                    <div className={styles.approveButtonContainer}>
                      <Button
                        onClick={onApprove}
                        size="sm"
                        className={styles.approveButton}
                      >
                        <Check size={16} />
                        Approve Plan
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
          {/* Show orchestrator tool calls (non-task tool calls) in the main chat */}
          {!isUser && orchestratorToolCalls.length > 0 && (
            <div className={styles.toolCalls}>
              <h4 className={styles.toolCallsHeader}>Tool Calls ({orchestratorToolCalls.length})</h4>
              {orchestratorToolCalls.map((toolCall: ToolCall) => (
                <ToolCallBox key={toolCall.id} toolCall={toolCall} />
              ))}
            </div>
          )}
          {/* Show sub-agent indicators (task tool calls delegate to sub-agents) */}
          {!isUser && subAgents.length > 0 && (
            <div className={styles.subAgents}>
              {subAgents.map((subAgent: SubAgent) => (
                <SubAgentIndicator
                  key={subAgent.id}
                  subAgent={subAgent}
                  onClick={() => onSelectSubAgent(subAgent)}
                />
              ))}
            </div>
          )}
          {/* Sub-agent tool calls are shown in the sub-agent panel when a sub-agent is selected */}
        </div>
      </div>
    );
  },
);

ChatMessage.displayName = "ChatMessage";
