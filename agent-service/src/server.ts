import express from "express";
import { z } from "zod";
import { config } from "./config.js";
import { generate } from "./agent.js";

const app = express();
app.use(express.json({ limit: "2mb" }));

const GenerateSchema = z.object({
  provider: z.enum(["ollama", "cloud"]),
  mode: z.enum(["qa", "ship30", "artifact"]),
  artifactType: z.enum(["markdown", "html"]),
  message: z.string().min(1),
  history: z.array(z.object({ role: z.string(), content: z.string() })).default([]),
  context: z.string().min(1)
});

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.post("/generate", async (req, res) => {
  const parsed = GenerateSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(422).json({ code: "VALIDATION_ERROR", issues: parsed.error.issues });
  }
  try {
    const result = await generate(parsed.data);
    return res.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "UNKNOWN_AGENT_ERROR";
    console.error(JSON.stringify({ event: "agent_generation_failed", message }));
    return res.status(503).json({ code: "AGENT_GENERATION_FAILED", message });
  }
});

app.listen(config.port, "0.0.0.0", () => {
  console.log(JSON.stringify({ event: "agent_service_started", port: config.port }));
});
