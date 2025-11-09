import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";

/**
 * Convert Markdown to LaTeX
 */
export function markdownToLatex(markdown: string): string {
  // Basic markdown to LaTeX conversion
  let latex = markdown;

  // Convert headers
  latex = latex.replace(/^### (.*$)/gim, "\\subsubsection{$1}");
  latex = latex.replace(/^## (.*$)/gim, "\\subsection{$1}");
  latex = latex.replace(/^# (.*$)/gim, "\\section{$1}");

  // Convert bold
  latex = latex.replace(/\*\*(.*?)\*\*/g, "\\textbf{$1}");
  latex = latex.replace(/__(.*?)__/g, "\\textbf{$1}");

  // Convert italic
  latex = latex.replace(/\*(.*?)\*/g, "\\textit{$1}");
  latex = latex.replace(/_(.*?)_/g, "\\textit{$1}");

  // Convert code blocks
  latex = latex.replace(/```[\s\S]*?```/g, (match) => {
    const code = match.replace(/```/g, "").trim();
    return `\\begin{verbatim}\n${code}\n\\end{verbatim}`;
  });

  // Convert inline code
  latex = latex.replace(/`([^`]+)`/g, "\\texttt{$1}");

  // Convert links [text](url)
  latex = latex.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "\\href{$2}{$1}");

  // Convert lists
  latex = latex.replace(/^\- (.*$)/gim, "\\item $1");
  latex = latex.replace(/^(\d+)\. (.*$)/gim, "\\item $2");

  // Wrap list items in itemize/enumerate
  const lines = latex.split("\n");
  let inList = false;
  let listType: "itemize" | "enumerate" | null = null;
  const result: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const isItem = line.trim().startsWith("\\item");

    if (isItem && !inList) {
      // Start a new list (determine type by checking if previous was numbered)
      listType = "itemize"; // Default to itemize, could be enhanced
      result.push("\\begin{itemize}");
      inList = true;
      result.push(line);
    } else if (isItem && inList) {
      result.push(line);
    } else if (!isItem && inList) {
      // End the list
      result.push(`\\end{${listType}}`);
      inList = false;
      listType = null;
      result.push(line);
    } else {
      result.push(line);
    }
  }

  if (inList && listType) {
    result.push(`\\end{${listType}}`);
  }

  latex = result.join("\n");

  // Convert line breaks
  latex = latex.replace(/\n\n/g, "\n\n");

  // Wrap in document structure
  return `\\documentclass{article}
\\usepackage[utf8]{inputenc}
\\usepackage{hyperref}
\\usepackage{verbatim}

\\begin{document}

${latex}

\\end{document}`;
}

/**
 * Convert Markdown to Word Document
 */
export async function markdownToWord(markdown: string, filename: string = "document"): Promise<Blob> {
  const paragraphs: (Paragraph | string)[] = [];
  const lines = markdown.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (!line) {
      // Empty line
      paragraphs.push(new Paragraph({ text: "" }));
      continue;
    }

    // Check for headers
    if (line.startsWith("# ")) {
      paragraphs.push(
        new Paragraph({
          text: line.substring(2),
          heading: HeadingLevel.HEADING_1,
        })
      );
    } else if (line.startsWith("## ")) {
      paragraphs.push(
        new Paragraph({
          text: line.substring(3),
          heading: HeadingLevel.HEADING_2,
        })
      );
    } else if (line.startsWith("### ")) {
      paragraphs.push(
        new Paragraph({
          text: line.substring(4),
          heading: HeadingLevel.HEADING_3,
        })
      );
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      // Bullet list
      paragraphs.push(
        new Paragraph({
          text: line.substring(2),
          bullet: {
            level: 0,
          },
        })
      );
    } else if (/^\d+\.\s/.test(line)) {
      // Numbered list - simplified for now
      const match = line.match(/^\d+\.\s(.*)/);
      if (match) {
        paragraphs.push(
          new Paragraph({
            text: match[1],
            // Numbering requires more complex setup, using simple paragraph for now
          })
        );
      }
    } else {
      // Regular paragraph - process inline formatting
      const runs = parseInlineFormatting(line);
      paragraphs.push(
        new Paragraph({
          children: runs,
        })
      );
    }
  }

  const doc = new Document({
    sections: [
      {
        properties: {},
        children: paragraphs.filter((p) => p !== "") as Paragraph[],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  return blob;
}

/**
 * Parse inline formatting (bold, italic, links, code) from markdown text
 */
function parseInlineFormatting(text: string): TextRun[] {
  const runs: TextRun[] = [];
  let currentIndex = 0;

  // Regex patterns for different formatting
  const patterns = [
    { regex: /\*\*(.*?)\*\*/g, style: { bold: true } },
    { regex: /__(.*?)__/g, style: { bold: true } },
    { regex: /\*(.*?)\*/g, style: { italics: true } },
    { regex: /_(.*?)_/g, style: { italics: true } },
    { regex: /`([^`]+)`/g, style: { font: "Courier New" } },
    { regex: /\[([^\]]+)\]\(([^)]+)\)/g, style: {} }, // Links
  ];

  // Find all matches
  const matches: Array<{
    index: number;
    length: number;
    text: string;
    style: any;
    isLink?: boolean;
    url?: string;
  }> = [];

  // Bold
  let match;
  const boldRegex = /\*\*(.*?)\*\*/g;
  while ((match = boldRegex.exec(text)) !== null) {
    matches.push({
      index: match.index,
      length: match[0].length,
      text: match[1],
      style: { bold: true },
    });
  }

  // Italic
  const italicRegex = /\*(.*?)\*/g;
  while ((match = italicRegex.exec(text)) !== null) {
    // Skip if it's part of a bold match
    const isPartOfBold = matches.some(
      (m) => m.index <= match!.index && match!.index < m.index + m.length
    );
    if (!isPartOfBold) {
      matches.push({
        index: match.index,
        length: match[0].length,
        text: match[1],
        style: { italics: true },
      });
    }
  }

  // Links
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  while ((match = linkRegex.exec(text)) !== null) {
    matches.push({
      index: match.index,
      length: match[0].length,
      text: match[1],
      style: { color: "0563C1", underline: {} },
      isLink: true,
      url: match[2],
    });
  }

  // Inline code
  const codeRegex = /`([^`]+)`/g;
  while ((match = codeRegex.exec(text)) !== null) {
    matches.push({
      index: match.index,
      length: match[0].length,
      text: match[1],
      style: { font: "Courier New" },
    });
  }

  // Sort matches by index
  matches.sort((a, b) => a.index - b.index);

  // Build runs
  for (const match of matches) {
    // Add text before match
    if (match.index > currentIndex) {
      const beforeText = text.substring(currentIndex, match.index);
      if (beforeText) {
        runs.push(new TextRun(beforeText));
      }
    }

    // Add formatted text
    if (match.isLink && match.url) {
      runs.push(
        new TextRun({
          text: match.text,
          style: "Hyperlink",
        })
      );
    } else {
      runs.push(new TextRun({ text: match.text, ...match.style }));
    }

    currentIndex = match.index + match.length;
  }

  // Add remaining text
  if (currentIndex < text.length) {
    const remainingText = text.substring(currentIndex);
    if (remainingText) {
      runs.push(new TextRun(remainingText));
    }
  }

  // If no matches, return single run
  if (runs.length === 0) {
    return [new TextRun(text)];
  }

  return runs;
}

