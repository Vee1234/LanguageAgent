// generate-word: word + language → shared card content, from the cache when anyone has added
// the word before, otherwise from ONE Gemini call (validated, then cached for everyone).
// The Gemini key and the service-role key live only here, as Supabase secrets.
// The cache logic itself is in logic.ts (unit-tested in app/src/server/resolveWord.test.ts).

import { createClient } from "npm:@supabase/supabase-js@2";
import {
  FIELDS,
  buildPrompt,
  normalizeKey,
  resolveWord,
  responseSchema,
  validate,
  type CardFields,
  type ResolveDeps,
  type SharedWord,
} from "./logic.ts";

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY");
const GEMINI_MODEL = Deno.env.get("GEMINI_MODEL") ?? "gemini-3.1-flash-lite";

// Service role: the only writer of shared words/notes/cards (users can only read them).
const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

type WordRow = { id: string; language: string; lemma: string; notes: { kind: string; body: string }[] };
const WORD_COLUMNS = "id, language, lemma, notes(kind, body)";

const toShared = (r: WordRow): SharedWord => ({
  id: r.id,
  language: r.language,
  lemma: r.lemma,
  notes: Object.fromEntries(r.notes.map((n) => [n.kind, n.body])),
});

async function loadWord(id: string): Promise<SharedWord> {
  const { data, error } = await db.from("words").select(WORD_COLUMNS).eq("id", id).single();
  if (error) throw error;
  return toShared(data as unknown as WordRow);
}

async function callGemini(word: string, language: string): Promise<CardFields> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY! },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: buildPrompt(word, language) }] }],
        generationConfig: { responseMimeType: "application/json", responseSchema, seed: 0 },
      }),
    },
  );
  if (!res.ok) {
    console.error("Gemini error", res.status, await res.text());
    throw new Error(`Gemini request failed (${res.status})`);
  }
  const data = await res.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (typeof text !== "string") throw new Error("Gemini returned no text");
  return validate(JSON.parse(text));
}

const deps: ResolveDeps = {
  async findByForm(language, formKey) {
    const { data, error } = await db
      .from("word_forms")
      .select(`words(${WORD_COLUMNS})`)
      .eq("language", language)
      .eq("form_key", formKey)
      .maybeSingle();
    if (error) throw error;
    const row = (data as unknown as { words: WordRow | null } | null)?.words;
    return row ? toShared(row) : null;
  },
  async findByLemma(language, lemmaKey) {
    const { data, error } = await db
      .from("words")
      .select(WORD_COLUMNS)
      .eq("language", language)
      .eq("lemma_key", lemmaKey)
      .maybeSingle();
    if (error) throw error;
    return data ? toShared(data as unknown as WordRow) : null;
  },
  generate: callGemini,
  async insertWord(language, fields) {
    const { data: id, error } = await db.rpc("insert_shared_word", {
      p_language: language,
      p_lemma: fields.lemma,
      p_lemma_key: normalizeKey(fields.lemma),
      p_fields: fields,
    });
    if (error) throw error;
    return loadWord(id as string);
  },
  async addForm(language, formKey, wordId) {
    const { error } = await db
      .from("word_forms")
      .upsert({ language, form_key: formKey, word_id: wordId }, {
        onConflict: "language,form_key",
        ignoreDuplicates: true,
      });
    if (error) throw error;
  },
};

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

  try {
    const { word: shared, source } = await resolveWord(word, language, deps);
    const notes = Object.fromEntries(
      FIELDS.filter((f) => f !== "lemma").map((f) => [f, shared.notes[f as keyof SharedWord["notes"]] ?? ""]),
    );
    return json({ word_id: shared.id, word, language, lemma: shared.lemma, source, ...notes });
  } catch (err) {
    console.error("generate-word failed", err);
    return json({ error: err instanceof Error ? err.message : "Could not generate the word" }, 502);
  }
});
