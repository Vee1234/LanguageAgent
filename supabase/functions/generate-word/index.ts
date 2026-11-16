// generate-word: word + language -> ONE Gemini call -> validated JSON card fields.
// Replaces the six separate calls in cardGenerators/LanguageUsageCardGenerator.py.
// The Gemini key lives only here, as a Supabase secret; the browser never sees it.

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY");
const GEMINI_MODEL = Deno.env.get("GEMINI_MODEL") ?? "gemini-3.1-flash-lite";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const FIELDS = [
  "lemma",
  "definition",
  "example",
  "register",
  "emotional_colour",
  "usage_conditions",
  "notable_use",
  "lyric",
] as const;
type Field = (typeof FIELDS)[number];
type CardFields = Record<Field, string>;

// Joos's five registers. Gemini must answer with exactly one of these words, in English.
const REGISTERS = ["Frozen", "Formal", "Consultative", "Casual", "Intimate"] as const;

// Same instructions as constants.py, merged into one request.
function buildPrompt(word: string, language: string): string {
  return `I am learning ${language} and want to create a flashcard for the word "${word}".
Write every field in ${language}, with no English translations or explanations.
Each value goes straight onto a flashcard, so include nothing but the requested content.

- lemma: the dictionary form of "${word}".
- definition: a short, single-sentence definition.
- example: one short sentence using "${word}" to show how it is used.
- register: the register the word is most typically used in. Output exactly one word, in English, from this list and nothing else — no description:
  - Frozen: fixed, ritualistic language that rarely changes (constitutions, prayers, anthems, statutes).
  - Formal: impersonal, serious, one-way language with strict grammar and no slang (papers, reports, official speeches).
  - Consultative: polite, professional two-way exchange when seeking help or expertise (doctor–patient, lawyer–client).
  - Casual: relaxed talk among peers and friends, with slang and contractions (texting, chatting with a teammate).
  - Intimate: private language between very close people, with pet names and inside jokes (partners, close family).
- emotional_colour: the feelings the word evokes, as a short fragment, not a sentence.
- usage_conditions: the situations and relationships the word is used in, as a short fragment. Do not name the register.
- notable_use: if the word appears in a well-known saying, proverb, work of literature, speech or song, quote that use in one line. If there is no such use, return exactly NONE. Never invent a use.
- lyric: one line from a well-known song that contains the word, with no title or artist. If you are not sure of a real line, return exactly NONE. Never invent one.`;
}

const responseSchema = {
  type: "OBJECT",
  properties: Object.fromEntries(
    FIELDS.map((f) => [
      f,
      f === "register" ? { type: "STRING", format: "enum", enum: [...REGISTERS] } : { type: "STRING" },
    ]),
  ),
  required: [...FIELDS],
  propertyOrdering: [...FIELDS],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function validate(raw: unknown): CardFields {
  if (typeof raw !== "object" || raw === null) throw new Error("Gemini did not return an object");
  const out = {} as CardFields;
  for (const field of FIELDS) {
    const value = (raw as Record<string, unknown>)[field];
    if (typeof value !== "string") throw new Error(`Gemini response is missing "${field}"`);
    const trimmed = value.trim();
    out[field] = trimmed === "NONE" ? "" : trimmed;
  }
  if (!out.lemma) throw new Error("Gemini returned an empty lemma");
  // Belt and braces: the schema enum should already guarantee this.
  if (!(REGISTERS as readonly string[]).includes(out.register)) {
    throw new Error(`Gemini returned an unknown register "${out.register}"`);
  }
  return out;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Use POST" }, 405);
  if (!GEMINI_API_KEY) return json({ error: "GEMINI_API_KEY secret is not set" }, 500);

  let word: string, language: string;
  try {
    const body = await req.json();
    word = String(body.word ?? "").trim();
    language = String(body.language ?? "").trim();
  } catch {
    return json({ error: "Body must be JSON: { word, language }" }, 400);
  }
  if (!word || word.length > 100) return json({ error: "word must be 1–100 characters" }, 400);
  if (!language || language.length > 50) return json({ error: "language must be 1–50 characters" }, 400);

  const geminiRes = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: buildPrompt(word, language) }] }],
        generationConfig: {
          responseMimeType: "application/json",
          responseSchema,
          seed: 0,
        },
      }),
    },
  );

  if (!geminiRes.ok) {
    const detail = await geminiRes.text();
    console.error("Gemini error", geminiRes.status, detail);
    return json({ error: `Gemini request failed (${geminiRes.status})` }, 502);
  }

  try {
    const data = await geminiRes.json();
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (typeof text !== "string") throw new Error("Gemini returned no text");
    return json({ word, language, ...validate(JSON.parse(text)) });
  } catch (err) {
    console.error("Bad Gemini response", err);
    return json({ error: err instanceof Error ? err.message : "Bad Gemini response" }, 502);
  }
});
