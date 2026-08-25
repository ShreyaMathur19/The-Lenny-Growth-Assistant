import path from "node:path";

export const config = {
  port: Number(process.env.PORT ?? 3001),
  ollamaBaseUrl: process.env.OLLAMA_BASE_URL ?? "http://ollama:11434",
  ollamaModel: process.env.OLLAMA_CHAT_MODEL ?? "llama3.2:3b",
  cloudProvider: process.env.CLOUD_PROVIDER ?? "anthropic",
  cloudModel: process.env.CLOUD_MODEL ?? "claude-sonnet-4-5",
  anthropicKey: process.env.ANTHROPIC_API_KEY ?? "",
  openaiKey: process.env.OPENAI_API_KEY ?? "",
  agentDir: path.resolve(process.cwd(), ".pi-agent"),
  skillsDir: path.resolve(process.cwd(), "skills")
};
