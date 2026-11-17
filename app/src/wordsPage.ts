import { supabase } from "./supabase";

// Supabase's API silently caps a response at 1,000 rows, so the list is always fetched in pages.
export const PAGE_SIZE = 50;

export type Note = { kind: string; body: string };
export type Word = {
  id: string;
  surface_form: string;
  lemma: string;
  language: string;
  created_at: string;
  notes: Note[];
};

/** Where the next page starts: just after the last word shown (newest first). */
export type Cursor = { created_at: string; id: string };

const COLUMNS = "id, surface_form, lemma, language, created_at, notes(kind, body)";

/**
 * Keyset filter for "older than the cursor". Id breaks ties between equal timestamps, so pages
 * never repeat or skip a word even if words are added (or later deleted) while scrolling.
 */
export function cursorFilter(c: Cursor): string {
  return `created_at.lt."${c.created_at}",and(created_at.eq."${c.created_at}",id.lt."${c.id}")`;
}

/** A full page may have more after it; a short page is the end. */
export function nextCursor(rows: { id: string; created_at: string }[]): Cursor | null {
  if (rows.length < PAGE_SIZE) return null;
  const last = rows[rows.length - 1];
  return { id: last.id, created_at: last.created_at };
}

/** Append a page, skipping anything already shown. */
export function mergePages<T extends { id: string }>(shown: T[], page: T[]): T[] {
  const ids = new Set(shown.map((w) => w.id));
  return [...shown, ...page.filter((w) => !ids.has(w.id))];
}

/**
 * One page of the signed-in user's words, newest first. `total` (the real number of words, counted
 * by the database) comes with the first page only; later pages return null.
 */
export async function fetchWordsPage(
  cursor: Cursor | null,
): Promise<{ rows: Word[]; total: number | null; cursor: Cursor | null }> {
  let query = supabase
    .from("words")
    .select(COLUMNS, cursor ? undefined : { count: "exact" })
    .order("created_at", { ascending: false })
    .order("id", { ascending: false })
    .limit(PAGE_SIZE);
  if (cursor) query = query.or(cursorFilter(cursor));

  const { data, error, count } = await query;
  if (error) throw new Error(error.message);
  const rows = (data ?? []) as Word[];
  return { rows, total: cursor ? null : (count ?? rows.length), cursor: nextCursor(rows) };
}
