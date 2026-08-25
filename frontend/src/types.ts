export type Source = {
  id: string;
  episode_title?: string | null;
  guest?: string | null;
  source_url?: string | null;
  source_path: string;
  excerpt: string;
  score?: number | null;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  provider?: string | null;
  model?: string | null;
  sources: Source[];
  created_at: string;
};

export type Artifact = {
  id: string;
  type: "markdown" | "html";
  title: string;
  content: string;
};

export type Session = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};
