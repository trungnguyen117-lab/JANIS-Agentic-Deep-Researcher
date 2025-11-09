/**
 * Utility functions for handling file content from deepagents format.
 * 
 * DeepAgents stores files in this format:
 * {
 *   "content": string[] | string,  // Array of lines or string
 *   "created_at": string,          // ISO timestamp
 *   "modified_at": string          // ISO timestamp
 * }
 */

/**
 * Extracts and normalizes file content from deepagents file data structure.
 * 
 * @param content - File content in various formats:
 *   - string: Already normalized, return as is
 *   - object with content array: Join array with newlines
 *   - object with content string: Return the string
 *   - other: Convert to string
 * 
 * @returns Normalized string content
 */
export function extractFileContent(content: any): string {
  // If it's already a string, return as is
  if (typeof content === "string") {
    return content;
  }

  // If it's an object, check for deepagents file format
  if (typeof content === "object" && content !== null) {
    // DeepAgents format: { content: string[], created_at: string, modified_at: string }
    if ("content" in content) {
      const fileContent = content.content;
      
      // If content is an array (deepagents format), join with newlines
      if (Array.isArray(fileContent)) {
        return fileContent.join("\n");
      }
      
      // If content is a string, return it
      if (typeof fileContent === "string") {
        return fileContent;
      }
    }
    
    // Fallback: try other common properties
    if ("text" in content && typeof content.text === "string") {
      return content.text;
    }
    
    if ("body" in content && typeof content.body === "string") {
      return content.body;
    }
    
    // Last resort: stringify the object (for debugging)
    try {
      return JSON.stringify(content, null, 2);
    } catch (error) {
      return String(content);
    }
  }

  // For any other type, convert to string
  return String(content || "");
}

/**
 * Checks if the content is in deepagents file format.
 */
export function isDeepAgentsFileFormat(content: any): boolean {
  return (
    typeof content === "object" &&
    content !== null &&
    "content" in content &&
    (Array.isArray(content.content) || typeof content.content === "string") &&
    ("created_at" in content || "modified_at" in content)
  );
}

