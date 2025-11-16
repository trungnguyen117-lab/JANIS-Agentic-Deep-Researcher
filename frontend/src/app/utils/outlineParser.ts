import { PlanOutline } from "../types/types";

/**
 * Extract outline from message content by looking for ```OUTLINE marker
 */
export function extractOutlineFromMessage(content: string): PlanOutline | null {
  if (!content) return null;
  
  // First, try to find JSON object with "sections" key anywhere in the content
  // This is the most reliable method - look for the actual JSON structure
  // Find the start of the JSON object
  const sectionsIndex = content.indexOf('"sections"');
  if (sectionsIndex !== -1) {
    // Find the opening brace before "sections"
    let startIndex = sectionsIndex;
    while (startIndex > 0 && content[startIndex] !== '{') {
      startIndex--;
    }
    
    if (content[startIndex] === '{') {
      // Find the matching closing brace
      let braceCount = 0;
      let endIndex = startIndex;
      for (let i = startIndex; i < content.length; i++) {
        if (content[i] === '{') braceCount++;
        if (content[i] === '}') {
          braceCount--;
          if (braceCount === 0) {
            endIndex = i;
            break;
          }
        }
      }
      
      if (endIndex > startIndex) {
        const jsonString = content.substring(startIndex, endIndex + 1);
        console.log("Found outline JSON via brace matching, length:", jsonString.length);
        const parsed = parseOutlineJSON(jsonString);
        if (parsed) {
          console.log("Successfully parsed outline with", parsed.sections.length, "sections");
          return parsed;
        }
      }
    }
  }
  
  // Fallback: try regex pattern matching
  const simplePattern = /\{\s*"sections"\s*:\s*\[[\s\S]{100,}?\]\s*(?:,\s*"metadata"\s*:\s*\{[\s\S]*?\})?\s*\}/;
  const jsonMatch = content.match(simplePattern);
  if (jsonMatch) {
    console.log("Found outline JSON via regex pattern, length:", jsonMatch[0].length);
    const parsed = parseOutlineJSON(jsonMatch[0]);
    if (parsed) {
      console.log("Successfully parsed outline with", parsed.sections.length, "sections");
      return parsed;
    }
  }
  
  // Pattern to match ```OUTLINE ... ``` (with 3 backticks)
  let pattern = /```OUTLINE\s*\n([\s\S]*?)\n```/;
  let match = content.match(pattern);
  
  if (!match) {
    // Try with 4 backticks (as specified in the prompt)
    pattern = /````OUTLINE\s*\n([\s\S]*?)\n````/;
    match = content.match(pattern);
  }
  
  if (!match) {
    // Try with escaped backticks or different formatting
    pattern = /```\s*OUTLINE\s*\n([\s\S]*?)\n\s*```/;
    match = content.match(pattern);
  }
  
  if (!match) {
    // Try to find any code block that might contain JSON with "sections"
    const codeBlockPattern = /```(?:json|OUTLINE)?\s*\n(\{[\s\S]*?"sections"[\s\S]*?\})\s*\n```/;
    match = content.match(codeBlockPattern);
  }
  
  if (match) {
    const jsonContent = match[1].trim();
    console.log("Extracted outline JSON from marker:", jsonContent.substring(0, 200));
    return parseOutlineJSON(jsonContent);
  }
  
  console.log("No outline found in message content");
  return null;
}

/**
 * Parse outline JSON string into PlanOutline object
 */
function parseOutlineJSON(jsonString: string): PlanOutline | null {
  try {
    // Try to fix common JSON issues
    let cleaned = jsonString.trim();
    
    // Remove markdown code block markers if present
    cleaned = cleaned.replace(/^```(?:json)?\s*\n?/gm, "");
    cleaned = cleaned.replace(/\n?```\s*$/gm, "");
    
    // Remove trailing commas
    cleaned = cleaned.replace(/,(\s*[}\]])/g, "$1");
    
    // Try to extract just the JSON object if there's extra text
    const jsonObjectMatch = cleaned.match(/\{[\s\S]*\}/);
    if (jsonObjectMatch) {
      cleaned = jsonObjectMatch[0];
    }
    
    const outline = JSON.parse(cleaned) as PlanOutline;
    
    // Validate structure
    if (!outline.sections || !Array.isArray(outline.sections)) {
      console.error("Outline missing sections array");
      return null;
    }
    
    // Ensure sections have required fields
    const validSections = outline.sections.filter(section => 
      section.id && section.title && section.description !== undefined && section.order !== undefined
    );
    
    if (validSections.length === 0) {
      console.error("No valid sections found in outline");
      return null;
    }
    
    console.log("Successfully parsed outline with", validSections.length, "sections");
    return {
      ...outline,
      sections: validSections,
    };
  } catch (error) {
    console.error("Failed to parse outline JSON:", error);
    console.error("JSON string was:", jsonString.substring(0, 500));
    return null;
  }
}

