import fs from "node:fs/promises";
import path from "node:path";
import {
  createAgentSession,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
  SettingsManager
} from "@earendil-works/pi-coding-agent";
import { config } from "./config.js";
import { buildSystemPrompt, buildUserPrompt, type Mode } from "./prompts.js";

export interface GenerateInput {
  provider: "ollama" | "cloud";
  mode: Mode;
  artifactType: "markdown" | "html";
  message: string;
  history: Array<{ role: string; content: string }>;
  context: string;
}

async function ensureModelsFile(): Promise<string> {
  await fs.mkdir(config.agentDir, { recursive: true });
  const modelsPath = path.join(config.agentDir, "models.json");
  const payload = {
    providers: {
      ollama: {
        baseUrl: `${config.ollamaBaseUrl.replace(/\/$/, "")}/v1`,
        api: "openai-completions",
        apiKey: "ollama",
        compat: {
          supportsDeveloperRole: false,
          supportsReasoningEffort: false
        },
        models: [
          {
            id: config.ollamaModel,
            name: `Ollama ${config.ollamaModel}`,
            reasoning: false,
            input: ["text"],
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
            contextWindow: 32768,
            maxTokens: 4096
          }
        ]
      }
    }
  };
  await fs.writeFile(modelsPath, JSON.stringify(payload, null, 2));
  return modelsPath;
}

async function createRuntime(): Promise<ModelRuntime> {
  const modelsPath = await ensureModelsFile();
  const runtime = await ModelRuntime.create({ modelsPath, allowModelNetwork: true, modelRefreshTimeoutMs: 8_000 });
  if (config.anthropicKey) await runtime.setRuntimeApiKey("anthropic", config.anthropicKey);
  if (config.openaiKey) await runtime.setRuntimeApiKey("openai", config.openaiKey);
  return runtime;
}

function cleanJson(raw: string): string {
  return raw.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
}

export async function generate(input: GenerateInput) {
  const modelRuntime = await createRuntime();
  const providerId = input.provider === "ollama" ? "ollama" : config.cloudProvider;
  const modelId = input.provider === "ollama" ? config.ollamaModel : config.cloudModel;
  const model = modelRuntime.getModel(providerId, modelId);
  if (!model) {
    throw new Error(`MODEL_NOT_FOUND: ${providerId}/${modelId}. Check CLOUD_MODEL or Ollama configuration.`);
  }

  if (input.provider === "cloud") {
    if (providerId === "anthropic" && !config.anthropicKey) throw new Error("MISSING_ANTHROPIC_API_KEY");
    if (providerId === "openai" && !config.openaiKey) throw new Error("MISSING_OPENAI_API_KEY");
  }

  const systemPrompt = await buildSystemPrompt(input.mode, input.artifactType);
  const settingsManager = SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 1 }
  });
  const loader = new DefaultResourceLoader({
    cwd: process.cwd(),
    agentDir: config.agentDir,
    settingsManager,
    systemPromptOverride: () => systemPrompt
  });
  await loader.reload();

  const { session } = await createAgentSession({
    cwd: process.cwd(),
    agentDir: config.agentDir,
    model,
    modelRuntime,
    resourceLoader: loader,
    sessionManager: SessionManager.inMemory(),
    settingsManager,
    noTools: "all",
    thinkingLevel: "off"
  });

  let text = "";
  const unsubscribe = session.subscribe((event: any) => {
    if (event.type === "message_update" && event.assistantMessageEvent?.type === "text_delta") {
      text += event.assistantMessageEvent.delta ?? "";
    }
  });

  try {
    await session.prompt(buildUserPrompt(input));
  } finally {
    unsubscribe();
    session.dispose();
  }

  if (!text.trim()) throw new Error("EMPTY_MODEL_RESPONSE");

  if (input.mode !== "artifact") {
    return { text: text.trim(), model: `${providerId}/${modelId}`, artifact: null };
  }

  try {
    const parsed = JSON.parse(cleanJson(text));
    if (!parsed?.artifact?.content || !parsed?.text) throw new Error("invalid artifact shape");
    return {
      text: String(parsed.text),
      model: `${providerId}/${modelId}`,
      artifact: {
        type: parsed.artifact.type === "html" ? "html" : "markdown",
        title: String(parsed.artifact.title ?? "Generated artifact"),
        content: String(parsed.artifact.content)
      }
    };
  } catch {
    return {
      text: "I generated the artifact, but the model did not follow the structured output contract exactly. The raw result is shown safely in the viewer.",
      model: `${providerId}/${modelId}`,
      artifact: { type: "markdown" as const, title: "Generated artifact", content: text.trim() }
    };
  }
}
