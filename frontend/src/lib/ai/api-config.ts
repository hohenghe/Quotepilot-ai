/**
 * API configuration — connects to any OpenAI-compatible API.
 * Set NEXT_PUBLIC_LLM_API_KEY to enable real AI; falls back to mock otherwise.
 */

let _apiKey = ""
let _baseUrl = ""
let _model = ""
let _embeddingModel = ""

function ensureConfig() {
  if (typeof window === "undefined") return
  _apiKey = process.env.NEXT_PUBLIC_LLM_API_KEY || ""
  _baseUrl = process.env.NEXT_PUBLIC_LLM_BASE_URL || "https://api.openai.com/v1"
  _model = process.env.NEXT_PUBLIC_LLM_MODEL || "gpt-4o-mini"
  _embeddingModel = process.env.NEXT_PUBLIC_EMBEDDING_MODEL || "text-embedding-3-small"
}

export function isLLMAvailable(): boolean {
  ensureConfig()
  return _apiKey.length > 0
}

export async function chatCompletion(
  systemPrompt: string,
  userMessage: string,
  jsonMode: boolean = false,
): Promise<string> {
  ensureConfig()

  const body: any = {
    model: _model,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userMessage },
    ],
    temperature: 0.3,
    max_tokens: 2000,
  }

  if (jsonMode) {
    body.response_format = { type: "json_object" }
  }

  const res = await fetch(`${_baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${_apiKey}`,
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API error ${res.status}: ${err}`)
  }

  const data = await res.json()
  return data.choices?.[0]?.message?.content || ""
}

export async function getEmbedding(text: string): Promise<number[]> {
  ensureConfig()

  const res = await fetch(`${_baseUrl}/embeddings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${_apiKey}`,
    },
    body: JSON.stringify({
      model: _embeddingModel,
      input: text,
    }),
  })

  if (!res.ok) {
    throw new Error(`Embedding API error ${res.status}`)
  }

  const data = await res.json()
  return data.data?.[0]?.embedding || []
}
