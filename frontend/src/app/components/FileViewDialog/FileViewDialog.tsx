"use client";

import React, { useMemo, useCallback, useState, useRef, useEffect } from "react";
import { FileText, Copy, Download, FileDown, ChevronDown } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { MarkdownContent } from "../MarkdownContent/MarkdownContent";
import type { FileItem } from "../../types/types";
import { markdownToLatex, markdownToWord } from "../../utils/exportUtils";
import { extractFileContent } from "../../utils/fileContentUtils";
import styles from "./FileViewDialog.module.scss";

interface FileViewDialogProps {
  file: FileItem;
  onClose: () => void;
}

export const FileViewDialog = React.memo<FileViewDialogProps>(
  ({ file, onClose }) => {
    const [showExportMenu, setShowExportMenu] = useState(false);
    const exportMenuRef = useRef<HTMLDivElement>(null);

    const fileExtension = useMemo(() => {
      return file.path.split(".").pop()?.toLowerCase() || "";
    }, [file.path]);

    const isMarkdown = useMemo(() => {
      return fileExtension === "md" || fileExtension === "markdown";
    }, [fileExtension]);

    const isLatex = useMemo(() => {
      return fileExtension === "tex";
    }, [fileExtension]);

    const isPdf = useMemo(() => {
      return fileExtension === "pdf";
    }, [fileExtension]);

    const isPaperFile = useMemo(() => {
      return file.path.startsWith("paper/");
    }, [file.path]);

    // Close export menu when clicking outside
    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (
          exportMenuRef.current &&
          !exportMenuRef.current.contains(event.target as Node)
        ) {
          setShowExportMenu(false);
        }
      };

      if (showExportMenu) {
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
          document.removeEventListener("mousedown", handleClickOutside);
        };
      }
    }, [showExportMenu]);

    const language = useMemo(() => {
      const languageMap: Record<string, string> = {
        js: "javascript",
        jsx: "javascript",
        ts: "typescript",
        tsx: "typescript",
        py: "python",
        rb: "ruby",
        go: "go",
        rs: "rust",
        java: "java",
        cpp: "cpp",
        c: "c",
        cs: "csharp",
        php: "php",
        swift: "swift",
        kt: "kotlin",
        scala: "scala",
        sh: "bash",
        bash: "bash",
        zsh: "bash",
        json: "json",
        xml: "xml",
        html: "html",
        css: "css",
        scss: "scss",
        sass: "sass",
        less: "less",
        sql: "sql",
        yaml: "yaml",
        yml: "yaml",
        toml: "toml",
        ini: "ini",
        dockerfile: "dockerfile",
        makefile: "makefile",
        tex: "latex",
      };
      return languageMap[fileExtension] || "text";
    }, [fileExtension]);

    const contentString = useMemo(() => {
      if (!file.content) {
        return "";
      }
      // Use utility function to extract content from deepagents format
      return extractFileContent(file.content);
    }, [file.content]);

    const handleCopy = useCallback(() => {
      if (contentString) {
        navigator.clipboard.writeText(contentString);
      }
    }, [contentString]);

    const handleDownload = useCallback(async () => {
      // For paper files, download from API endpoint
      if (isPaperFile) {
        const { getDeployment } = await import("@/lib/environment/deployments");
        const deployment = getDeployment();
        
        if (isLatex) {
          window.open(`${deployment.deploymentUrl}/api/paper/latex`, '_blank');
        } else if (isPdf) {
          window.open(`${deployment.deploymentUrl}/api/paper/pdf`, '_blank');
        }
        return;
      }
      
      // For other files, download from content
      if (contentString) {
        const blob = new Blob([contentString], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = file.path;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    }, [contentString, file.path, isPaperFile, isLatex, isPdf]);

    const handleExportMarkdown = useCallback(() => {
      handleDownload();
      setShowExportMenu(false);
    }, [handleDownload]);

    const handleExportLatex = useCallback(async () => {
      if (!contentString || !isMarkdown) return;
      try {
        const latex = markdownToLatex(contentString);
        const blob = new Blob([latex], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = file.path.replace(/\.(md|markdown)$/i, ".tex");
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setShowExportMenu(false);
      } catch (error) {
        console.error("Error exporting to LaTeX:", error);
        alert("Error exporting to LaTeX. Please try again.");
      }
    }, [contentString, file.path, isMarkdown]);

    const handleExportWord = useCallback(async () => {
      if (!contentString || !isMarkdown) return;
      try {
        const blob = await markdownToWord(contentString, file.path);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = file.path.replace(/\.(md|markdown)$/i, ".docx");
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setShowExportMenu(false);
      } catch (error) {
        console.error("Error exporting to Word:", error);
        alert("Error exporting to Word. Please try again.");
      }
    }, [contentString, file.path, isMarkdown]);

    return (
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className={styles.dialog}>
          <DialogTitle className="sr-only">{file.path}</DialogTitle>
          <div className={styles.header}>
            <div className={styles.titleSection}>
              <FileText className={styles.fileIcon} />
              <span className={styles.fileName}>{file.path}</span>
            </div>
            <div className={styles.actions}>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className={styles.actionButton}
              >
                <Copy size={16} />
                Copy
              </Button>
              {isMarkdown ? (
                <div
                  ref={exportMenuRef}
                  style={{ position: "relative", display: "inline-block" }}
                >
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowExportMenu(!showExportMenu)}
                    className={styles.actionButton}
                  >
                    <FileDown size={16} />
                    Export
                    <ChevronDown size={14} style={{ marginLeft: "4px" }} />
                  </Button>
                  {showExportMenu && (
                    <div
                      style={{
                        position: "absolute",
                        top: "100%",
                        right: 0,
                        marginTop: "4px",
                        backgroundColor: "white",
                        border: "1px solid #e5e7eb",
                        borderRadius: "6px",
                        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                        zIndex: 1000,
                        minWidth: "150px",
                      }}
                    >
                      <button
                        onClick={handleExportMarkdown}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          textAlign: "left",
                          border: "none",
                          background: "none",
                          cursor: "pointer",
                          fontSize: "14px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = "#f3f4f6";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = "white";
                        }}
                      >
                        <Download size={14} />
                        Markdown (.md)
                      </button>
                      <button
                        onClick={handleExportLatex}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          textAlign: "left",
                          border: "none",
                          background: "none",
                          cursor: "pointer",
                          fontSize: "14px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          borderTop: "1px solid #e5e7eb",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = "#f3f4f6";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = "white";
                        }}
                      >
                        <FileDown size={14} />
                        LaTeX (.tex)
                      </button>
                      <button
                        onClick={handleExportWord}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          textAlign: "left",
                          border: "none",
                          background: "none",
                          cursor: "pointer",
                          fontSize: "14px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          borderTop: "1px solid #e5e7eb",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = "#f3f4f6";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = "white";
                        }}
                      >
                        <FileDown size={14} />
                        Word (.docx)
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDownload}
                    className={styles.actionButton}
                  >
                    <Download size={16} />
                    Download
                  </Button>
                  {isLatex && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={async () => {
                        const { getDeployment } = await import("@/lib/environment/deployments");
                        const deployment = getDeployment();
                        try {
                          // Try to download PDF directly first
                          const pdfResponse = await fetch(`${deployment.deploymentUrl}/api/paper/pdf`);
                          if (pdfResponse.ok) {
                            const blob = await pdfResponse.blob();
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = "paper_v4_final.pdf";
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            window.URL.revokeObjectURL(url);
                          } else {
                            // If PDF doesn't exist, try to convert
                            const convertResponse = await fetch(`${deployment.deploymentUrl}/api/paper/convert-to-pdf`);
                            if (convertResponse.ok) {
                              const blob = await convertResponse.blob();
                              const url = window.URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = "paper_v4_final.pdf";
                              document.body.appendChild(a);
                              a.click();
                              document.body.removeChild(a);
                              window.URL.revokeObjectURL(url);
                            } else {
                              const error = await convertResponse.json();
                              alert(`Failed to get PDF: ${error.detail || 'PDF not available. Try converting first.'}`);
                            }
                          }
                        } catch (error) {
                          alert(`Error getting PDF: ${error}`);
                        }
                      }}
                      className={styles.actionButton}
                    >
                      <FileDown size={16} />
                      Download PDF
                    </Button>
                  )}
                </>
              )}
            </div>
          </div>

          <div className={styles.contentArea}>
            {isPdf && isPaperFile ? (
              <div style={{ padding: "2rem", textAlign: "center" }}>
                <p style={{ marginBottom: "1rem", color: "var(--color-text-secondary)" }}>
                  PDF files cannot be displayed inline. Click "Download" to view the PDF.
                </p>
              </div>
            ) : contentString ? (
              isMarkdown ? (
                <div className={styles.markdownWrapper}>
                  <MarkdownContent content={contentString} />
                </div>
              ) : (
                <div style={{ overflow: "auto", width: "100%" }}>
                  <SyntaxHighlighter
                    language={language}
                    style={oneDark}
                    customStyle={{
                      margin: 0,
                      borderRadius: "0.5rem",
                      fontSize: "0.875rem",
                      overflow: "auto",
                      maxWidth: "100%",
                    }}
                    showLineNumbers
                    wrapLines
                    wrapLongLines
                  >
                    {contentString}
                  </SyntaxHighlighter>
                </div>
              )
            ) : (
              <div className={styles.emptyContent}>
                <p>File is empty</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    );
  },
);

FileViewDialog.displayName = "FileViewDialog";
