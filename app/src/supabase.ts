import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const configError =
  !url || !anonKey ? "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in app/.env.local" : null;

export const supabase = createClient(url ?? "http://localhost", anonKey ?? "missing");

/** Must match REGISTERS in supabase/functions/generate-word and the notes_register_value check. */
export const REGISTERS = ["Frozen", "Formal", "Consultative", "Casual", "Intimate"] as const;

/** The fields generate-word returns, in display order. */
export const CARD_FIELDS = [
  { key: "definition", label: "Definition" },
  { key: "example", label: "Example" },
  { key: "register", label: "Register" },
  { key: "emotional_colour", label: "Emotional colour" },
  { key: "usage_conditions", label: "When it's used" },
  { key: "notable_use", label: "Notable use" },
  { key: "lyric", label: "Lyric" },
] as const;

export type FieldKey = (typeof CARD_FIELDS)[number]["key"];

/** What generate-word returns: shared content for the word, plus the form the user typed. */
export type GeneratedCard = {
  word_id: string;
  word: string;
  language: string;
  lemma: string;
  source: "cache" | "lemma" | "generated";
} & Record<FieldKey, string>;
