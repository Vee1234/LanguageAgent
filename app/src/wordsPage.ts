import { supabase } from "./supabase";
import { toWordList, type UserCardRow, type WordListItem } from "./cards";

// Supabase's API silently caps a response at 1,000 rows, so the list is always fetched in pages (L3).
export const PAGE_SIZE = 50;

export type Word = WordListItem;

/** Where the next page starts: just after the last card shown (newest first). */
export type Cursor = { created_at: string; card_id: string };

// The user's cards, with the shared word and notes, and their own notes on that word.
const COLUMNS =
  "card_id, surface_form, created_at, cards(words(id, language, lemma, notes(kind, body), user_notes(kind, body)))";

/**
 * Keyset filter on user_cards for "older than the cursor". card_id breaks ties between equal
 * timestamps, so pages never repeat or skip a word even if words are added (or later deleted).
 */
export function cursorFilter(c: Cursor): string {
  return `created_at.lt."${c.created_at}",and(created_at.eq."${c.created_at}",card_id.lt."${c.card_id}")`;
}

/** A full page may have more after it; a short page is the end. */
export function nextCursor(rows: { card_id: string; created_at: string }[]): Cursor | null {
  if (rows.length < PAGE_SIZE) return null;
  const last = rows[rows.length - 1];
  return { card_id: last.card_id, created_at: last.created_at };
}

/** Append a page, skipping anything already shown. */
export function mergePages<T extends { id: string }>(shown: T[], page: T[]): T[] {
  const ids = new Set(shown.map((w) => w.id));
  return [...shown, ...page.filter((w) => !ids.has(w.id))];
}

/**
 * One page of the signed-in user's words, newest first. `total` (the real number of cards, counted
 * by the database) comes with the first page only; later pages return null.
 */
export async function fetchWordsPage(
  cursor: Cursor | null,
): Promise<{ rows: Word[]; total: number | null; cursor: Cursor | null }> {
  let query = supabase
    .from("user_cards")
    .select(COLUMNS, cursor ? undefined : { count: "exact" })
    .order("created_at", { ascending: false })
    .order("card_id", { ascending: false })
    .limit(PAGE_SIZE);
  if (cursor) query = query.or(cursorFilter(cursor));

  const { data, error, count } = await query;
  if (error) throw new Error(error.message);
  const raw = (data ?? []) as unknown as UserCardRow[];
  return { rows: toWordList(raw), total: cursor ? null : (count ?? raw.length), cursor: nextCursor(raw) };
}
