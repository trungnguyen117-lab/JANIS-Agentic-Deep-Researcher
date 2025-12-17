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

  try {
    const paperDir = getPaperDir(threadId);
    const texPath = path.join(paperDir, "paper_v4_final.tex");
    const content = await fs.readFile(texPath, "utf-8");
    return new NextResponse(content, {
      status: 200,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
      },
    });
  } catch (error: any) {
    const message =
      error?.code === "ENOENT"
        ? "LaTeX file not found. Paper may not be generated yet."
        : `Failed to read LaTeX file: ${error?.message || String(error)}`;
    return NextResponse.json({ error: message }, { status: 404 });
  }
}


