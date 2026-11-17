// Pure logic for generate-word: no Deno or Supabase imports, so it can be unit-tested
// (app/src/server/resolveWord.test.ts). index.ts wires it to Gemini and the database.

export const FIELDS = [
  "lemma",
  "definition",
  "example",
  "register",
  "emotional_colour",
  "usage_conditions",
  "notable_use",
  "lyric",
] as const;
export type Field = (typeof FIELDS)[number];
export type CardFields = Record<Field, string>;

// Joos's five registers. Gemini must answer with exactly one of these words, in English.
export const REGISTERS = ["Frozen", "Formal", "Consultative", "Casual", "Intimate"] as const;

/** Shared, user-independent word content as stored in the cache. */
export type SharedWord = {
  id: string;
  language: string;
  lemma: string;
  notes: Partial<Record<Exclude<Field, "lemma">, string>>;
};

/** Where the word came from: a known form, a known lemma after one Gemini call, or newly generated. */
export type Source = "cache" | "lemma" | "generated";

export type ResolveDeps = {
  findByForm(language: string, formKey: string): Promise<SharedWord | null>;
  findByLemma(language: string, lemmaKey: string): Promise<SharedWord | null>;
  generate(word: string, language: string): Promise<CardFields>;
  insertWord(language: string, fields: CardFields): Promise<SharedWord>;
  addForm(language: string, formKey: string, wordId: string): Promise<void>;
};

/** Cache key for a word or form: trimmed, Unicode-NFC, lower-case. */
export function normalizeKey(s: string): string {
  return s.trim().normalize("NFC").toLowerCase();
}

/**
 * Finds shared content for `word`, calling Gemini only when no user has added it before.
 * 1. A form seen before ("maisons") → cached word, no Gemini call.
 * 2. Otherwise Gemini gives the lemma; if that lemma is cached, reuse it (Gemini's new text is discarded
 *    so everyone sees the same content) and remember the new form.
 * 3. Otherwise store the new word and remember both the typed form and the lemma.
 */
export async function resolveWord(
  word: string,
  language: string,
  deps: ResolveDeps,
): Promise<{ word: SharedWord; source: Source }> {
  const formKey = normalizeKey(word);

  const cached = await deps.findByForm(language, formKey);
  if (cached) return { word: cached, source: "cache" };

  const fields = await deps.generate(word, language);
  const lemmaKey = normalizeKey(fields.lemma);

  const existing = await deps.findByLemma(language, lemmaKey);
  if (existing) {
    await deps.addForm(language, formKey, existing.id);
    return { word: existing, source: "lemma" };
  }

  const created = await deps.insertWord(language, fields);
  await deps.addForm(language, formKey, created.id);
  if (lemmaKey !== formKey) await deps.addForm(language, lemmaKey, created.id);
  return { word: created, source: "generated" };
}

// Same instructions as constants.py, merged into one request.
export function buildPrompt(word: string, language: string): string {
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

export const responseSchema = {
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

/** Gemini output is untrusted: check every field before it is cached for all users. */
export function validate(raw: unknown): CardFields {
  if (typeof raw !== "object" || raw === null) throw new Error("Gemini did not return an object");
  const out = {} as CardFields;
  for (const field of FIELDS) {
    const value = (raw as Record<string, unknown>)[field];
    if (typeof value !== "string") throw new Error(`Gemini response is missing "${field}"`);
    const trimmed = value.trim();
    out[field] = trimmed === "NONE" ? "" : trimmed;
  }
  if (!out.lemma) throw new Error("Gemini returned an empty lemma");
  if (!(REGISTERS as readonly string[]).includes(out.register)) {
    throw new Error(`Gemini returned an unknown register "${out.register}"`);
  }
  return out;
}
