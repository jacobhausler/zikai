// zikai-tool.ts — Vercel AI SDK tool (ai@4; `npm i ai zod`). Mirrors zikai/client.py:
// two env vars, one timeout, one retry on network flake, fail-open "oracle: unavailable".
import { tool } from "ai";
import { z } from "zod";

const BASE = (process.env.ZIKAI_URL ?? "http://127.0.0.1:8077").replace(/\/+$/, "");
const KEY = process.env.ZIKAI_KEY ?? "";
export const UNAVAILABLE = "oracle: unavailable"; // the one fail-open string, repo-wide

async function decide(text: string, retry = true): Promise<any> {
  const opts = { method: "POST",
    headers: { "content-type": "application/json", ...(KEY ? { "x-api-key": KEY } : {}) },
    body: JSON.stringify({ text, level: "compact", trace: false }),
    signal: AbortSignal.timeout(8000) }; // edge-safe fetch, mirrors client.py's timeout
  let res: Response;
  try { res = await fetch(`${BASE}/decide`, opts); }
  catch { if (retry) return decide(text, false); throw new Error("zikai: network"); }
  if (!res.ok) throw new Error(`zikai: ${res.status}`); // 4xx is a verdict, not a flake
  return await res.json();
}
export const zikaiOracle = tool({
  description: "Return the chengyu (Chinese idiom) most applicable to a situation, formatted '博古通今 (bó gǔ tōng jīn) — gloss'.",
  parameters: z.object({ text: z.string().describe("The situation you need an idiom for.") }),
  execute: async ({ text }: { text: string }) => {
    try { const i = (await decide(text)).idiom ?? {};
      return `${i.hanzi ?? i.slug ?? "?"} (${i.pinyin ?? ""}) — ${((i.meaning ?? "") as string).split(". ")[0]}`;
    } catch { return UNAVAILABLE; } // fail-open: the agent stream proceeds ungarnished
  },
});
