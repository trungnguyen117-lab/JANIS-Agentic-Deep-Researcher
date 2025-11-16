export interface ToolCall {
  id: string;
  name: string;
  args: any;
  result?: string;
  status: "pending" | "completed" | "error";
  subagentType?: string; // For sub-agent tool calls
  parentToolCallId?: string; // ID of the parent task tool call
}

export interface SubAgent {
  id: string;
  name: string;
  subAgentName: string;
  input: any;
  output?: any;
  status: "pending" | "active" | "completed" | "error";
}

export interface FileItem {
  path: string;
  content: string;
}

export interface TodoItem {
  id: string;
  content: string;
  status: "pending" | "in_progress" | "completed";
  createdAt?: Date;
  updatedAt?: Date;
}

export interface Thread {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface SubSection {
  id: string;
  title: string;
  description: string;
  order: number;
}

export interface Section {
  id: string;
  title: string;
  description: string;
  order: number;
  researchTasks?: string[];
  estimatedDepth?: string;
  subsections?: SubSection[];
}

export interface PlanOutline {
  sections: Section[];
  metadata?: {
    totalSections?: number;
    estimatedTotalPages?: number;
    [key: string]: any;
  };
}
