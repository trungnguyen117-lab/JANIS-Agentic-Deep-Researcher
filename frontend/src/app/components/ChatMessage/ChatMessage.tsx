"use client";

import React, { useEffect, useMemo } from "react";
import { User, Bot, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubAgentIndicator } from "../SubAgentIndicator/SubAgentIndicator";
import { ToolCallBox } from "../ToolCallBox/ToolCallBox";
import { MarkdownContent } from "../MarkdownContent/MarkdownContent";
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
}

export const ChatMessage = React.memo<ChatMessageProps>(
  ({ message, toolCalls, subagentToolCalls = [], showAvatar, onSelectSubAgent, selectedSubAgent, onApprove }) => {
    const isUser = message.type === "human";
    const messageContent = extractStringFromMessageContent(message);
    const hasContent = messageContent && messageContent.trim() !== "";
    const hasToolCalls = toolCalls.length > 0;
    
    // Extract sub-agents from tool calls
    const subAgents = useMemo(() => {
      return toolCalls
        .filter((toolCall: ToolCall) => {
          return (
            toolCall.name === "task" &&
            toolCall.args["subagent_type"] &&
            toolCall.args["subagent_type"] !== "" &&
            toolCall.args["subagent_type"] !== null
          );
        })
        .map((toolCall: ToolCall) => {
          return {
            id: toolCall.id,
            name: toolCall.name,
            subAgentName: toolCall.args["subagent_type"],
            input: toolCall.args["description"],
            output: toolCall.result,
            status: toolCall.status,
          };
        });
    }, [toolCalls]);

    // Detect if this message is from the planning-agent
    const isPlanProposal = useMemo(() => {
      if (isUser || !messageContent) return false;
      // Check if any sub-agent in this message is the planning-agent
      const hasPlanningAgent = subAgents.some(
        (subAgent: SubAgent) => subAgent.subAgentName === "planning-agent"
      );
      return hasPlanningAgent;
    }, [isUser, messageContent, subAgents]);

    const subAgentsString = useMemo(() => {
      return JSON.stringify(subAgents);
    }, [subAgents]);

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
          {hasToolCalls && (
            <div className={styles.toolCalls}>
              {toolCalls.map((toolCall: ToolCall) => {
                if (toolCall.name === "task") return null;
                return <ToolCallBox key={toolCall.id} toolCall={toolCall} />;
              })}
            </div>
          )}
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
          {!isUser && subagentToolCalls.length > 0 && (
            <div className={styles.subagentToolCalls}>
              <div className={styles.subagentToolCallsHeader}>
                <span className={styles.subagentToolCallsTitle}>
                  Tools used by sub-agents:
                </span>
              </div>
              {subagentToolCalls.map((toolCall: ToolCall) => (
                <div key={toolCall.id} className={styles.subagentToolCall}>
                  <span className={styles.subagentToolCallLabel}>
                    {toolCall.subagentType}: 
                  </span>
                  <ToolCallBox toolCall={toolCall} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  },
);

ChatMessage.displayName = "ChatMessage";
