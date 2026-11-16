import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const configError =
  !url || !anonKey ? "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in app/.env.local" : null;

export const supabase = createClient(url ?? "http://localhost", anonKey ?? "missing");

/** The fields generate-word returns, in display order. */
export const CARD_FIELDS = [
  { key: "definition", label: "Definition" },
  { key: "example", label: "Example" },
  { key: "emotional_colour", label: "Emotional colour" },
  { key: "usage_conditions", label: "When it's used" },
  { key: "notable_use", label: "Notable use" },
  { key: "lyric", label: "Lyric" },
] as const;

export type FieldKey = (typeof CARD_FIELDS)[number]["key"];

export type GeneratedCard = {
  word: string;
  language: string;
  lemma: string;
} & Record<FieldKey, string>;
