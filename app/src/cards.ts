// Turning the shared-cache rows into what the app shows, and the user's edits into personal notes.

import { CARD_FIELDS } from "./supabase";

export type Note = { kind: string; body: string };

/** One row of `user_cards` with its shared card → word → notes, and the user's own notes. */
export type UserCardRow = {
  card_id: string;
  surface_form: string;
  created_at: string;
  cards: {
    words: {
      id: string;
      language: string;
      lemma: string;
      notes: Note[];
      user_notes: Note[];
    };
  };
};

export type WordListItem = {
  id: string;
  surface_form: string;
  lemma: string;
  language: string;
  created_at: string;
  notes: Note[];
};

/** One entry per word; the user's own note replaces the shared note of the same kind. */
export function toWordList(rows: UserCardRow[]): WordListItem[] {
  const seen = new Set<string>();
  const out: WordListItem[] = [];
  for (const row of rows) {
    const w = row.cards.words;
    if (seen.has(w.id)) continue;
    seen.add(w.id);
    const mine = new Map(w.user_notes.map((n) => [n.kind, n.body]));
    const notes = w.notes.map((n) => ({ kind: n.kind, body: mine.get(n.kind) ?? n.body }));
    for (const [kind, body] of mine) {
      if (!w.notes.some((n) => n.kind === kind)) notes.push({ kind, body });
    }
    out.push({
      id: w.id,
      surface_form: row.surface_form,
      lemma: w.lemma,
      language: w.language,
      created_at: row.created_at,
      notes,
    });
  }
  return out;
}

/**
 * The fields the user changed on the review screen, trimmed. These become personal notes;
 * shared content is never edited. A cleared field is ignored, so the shared note still shows.
 */
export function userEdits(
  generated: Record<string, string>,
  edited: Record<string, string>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [kind, value] of Object.entries(edited)) {
    const body = (value ?? "").trim();
    if (body && body !== (generated[kind] ?? "").trim()) out[kind] = body;
  }
  return out;
}

/** The fields every card must show (Std 1): a value, or visibly missing (L8). */
export const REQUIRED_FIELDS = ["definition", "example", "register", "emotional_colour"] as const;

const FIELDS = [...CARD_FIELDS, { key: "user", label: "My note" }];

export type CardField = {
  key: string;
  label: string;
  value: string | null; // null when missing: never a default
  missing: boolean;
  required: boolean;
  mine: boolean; // the user's own note, not the shared one
};

/**
 * What a card shows, in display order. The four required fields are always there, with a value
 * or marked missing; other fields appear only when they have a value. The user's own note for a
 * field wins over the shared one. An empty or whitespace-only note counts as missing.
 */
export function cardFields(notes: Note[], userNotes: Note[] = []): CardField[] {
  const filled = (list: Note[], kind: string) => list.find((n) => n.kind === kind && n.body.trim())?.body.trim();
  const out: CardField[] = [];
  for (const { key, label } of FIELDS) {
    const mine = filled(userNotes, key);
    const value = mine ?? filled(notes, key) ?? null;
    const required = (REQUIRED_FIELDS as readonly string[]).includes(key);
    if (value === null && !required) continue;
    out.push({ key, label, value, missing: value === null, required, mine: mine !== undefined });
  }
  return out;
}
