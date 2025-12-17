import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

function getPaperDir(threadId: string | null): string {
  // From frontend folder, project root is one level up
  const projectRoot = path.resolve(process.cwd(), "..");
  if (threadId) {
    return path.join(projectRoot, "project", "threads", threadId, "paper");
  }
  return path.join(projectRoot, "project", "paper");
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const threadId = searchParams.get("thread_id");
  const requestedFilename = searchParams.get("filename") || "paper_v4_final.pdf";
  // Prevent path traversal – only allow basename
  const safeFilename = path.basename(requestedFilename) || "paper_v4_final.pdf";

  try {
    const paperDir = getPaperDir(threadId);
    const pdfPath = path.join(paperDir, safeFilename);
    const fileBuffer = await fs.readFile(pdfPath);

    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="paper_v4_final.pdf"',
      },
    });
  } catch (error: any) {
    const message =
      error?.code === "ENOENT"
        ? "PDF file not found. Paper may not be generated yet."
        : `Failed to read PDF file: ${error?.message || String(error)}`;
    return NextResponse.json({ error: message }, { status: 404 });
  }
}


