"use client";

import React, { useEffect, useMemo } from "react";
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
      // Debug: Log all tool calls to see their structure
      console.log("[ChatMessage] All tool calls:", {
        messageId: message.id,
        toolCallsCount: toolCalls.length,
        toolCalls: toolCalls.map(tc => ({
          id: tc.id,
          name: tc.name,
          args: tc.args,
          status: tc.status,
          hasResult: !!tc.result,
        })),
      });
      
      const filtered = toolCalls
        .filter((toolCall: ToolCall) => {
          const isTask = toolCall.name === "task";
          const hasSubagentType = toolCall.args && (
            toolCall.args["subagent_type"] ||
            toolCall.args["subagentType"] ||
            toolCall.args.subagent_type
          );
          
          // Debug: Log why tool calls are filtered out
          if (!isTask) {
            console.log("[ChatMessage] Tool call filtered: not a task", { name: toolCall.name });
          } else if (!hasSubagentType) {
            console.log("[ChatMessage] Tool call filtered: no subagent_type", { 
              name: toolCall.name, 
              args: toolCall.args,
              argsKeys: toolCall.args ? Object.keys(toolCall.args) : [],
            });
          }
          
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
      
      // Debug: Log sub-agents for this message
      console.log("[ChatMessage] Extracted sub-agents:", {
        messageId: message.id,
        toolCallsCount: toolCalls.length,
        subAgentsCount: filtered.length,
        subAgents: filtered.map(sa => ({
          id: sa.id,
          name: sa.subAgentName,
          status: sa.status,
          hasOutput: !!sa.output,
          outputLength: sa.output?.length || 0,
        })),
        fullSubAgents: filtered, // Include full objects for inspection
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
      
      console.log("[ChatMessage] Plan proposal check:", {
        messageId: message.id,
        isUser,
        hasContent: !!messageContent,
        hasPlanningAgent,
        planningAgentCount: planningAgentSubAgents.length,
        hasOutline,
        allSubAgentsCount: subAgents.length,
        allSubAgentNames: subAgents.map(sa => sa.subAgentName),
        planningAgentSubAgents: planningAgentSubAgents.map(sa => ({
          id: sa.id,
          name: sa.subAgentName,
          status: sa.status,
          hasOutput: !!sa.output,
          outputLength: sa.output?.length || 0,
        })),
      });
      
      // Show approve button if:
      // 1. There's a planning-agent sub-agent (task was delegated), AND
      // 2. Either the outline file exists OR at least one planning-agent task has completed with output
      // Note: We don't require messageContent because the message might only have tool calls initially
      if (!hasPlanningAgent) {
        return false;
      }
      
      // If outline file exists, that's a strong indicator the plan is ready
      if (hasOutline) {
        console.log("[ChatMessage] Plan proposal detected: outline file exists");
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
      
      if (hasCompletedPlanningAgent) {
        console.log("[ChatMessage] Plan proposal detected: planning-agent completed");
      }
      
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
        if (!isTaskCall) {
          console.log("[ChatMessage] Including orchestrator tool call:", {
            id: toolCall.id,
            name: toolCall.name,
            status: toolCall.status,
          });
        }
        return !isTaskCall;
      });
      
      // Debug: Log orchestrator tool calls
      console.log("[ChatMessage] Orchestrator tool calls summary:", {
        messageId: message.id,
        totalToolCalls: toolCalls.length,
        orchestratorToolCallsCount: filtered.length,
        isUser,
        willRender: !isUser && filtered.length > 0,
        orchestratorToolCalls: filtered.map(tc => ({
          id: tc.id,
          name: tc.name,
          status: tc.status,
          hasResult: !!tc.result,
        })),
      });
      
      return filtered;
    }, [toolCalls, message.id, isUser]);

    useEffect(() => {
      if (
        subAgents.some(
          (subAgent: SubAgent) => subAgent.id === selectedSubAgent?.id,
        )
      ) {
        onSelectSubAgent(
          subAgents.find(
            (subAgent: SubAgent) => subAgent.id === selectedSubAgent?.id,
          )!,
        );
      }
    }, [selectedSubAgent, onSelectSubAgent, subAgentsString]);

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
              {orchestratorToolCalls.map((toolCall: ToolCall) => {
                console.log("[ChatMessage] Rendering orchestrator tool call:", {
                  id: toolCall.id,
                  name: toolCall.name,
                  status: toolCall.status,
                });
                return <ToolCallBox key={toolCall.id} toolCall={toolCall} />;
              })}
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
