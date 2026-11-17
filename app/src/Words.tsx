import { useCallback, useEffect, useRef, useState } from "react";
import { CARD_FIELDS } from "./supabase";
import { fetchWordsPage, mergePages, type Cursor, type Word } from "./wordsPage";

const LABELS: Record<string, string> = {
  ...Object.fromEntries(CARD_FIELDS.map(({ key, label }) => [key, label])),
  user: "My note",
};
const ORDER = [...CARD_FIELDS.map((f) => f.key as string), "user"];

/**
 * The user's words, newest first, loaded a page at a time; scrolling to the bottom (or
 * "Load more") fetches the next page. `version` changes after every save and restarts from page one.
 */
export default function Words({ version }: { version: number }) {
  const [words, setWords] = useState<Word[] | null>(null);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<Cursor | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null); // first page failed: nothing to show
  const [moreError, setMoreError] = useState<string | null>(null); // a later page failed: keep the list
  const [attempt, setAttempt] = useState(0); // bumped by Retry to rerun the first-page read
  const [openId, setOpenId] = useState<string | null>(null);
  // Bumped on every restart (and on unmount); a response from an older generation is ignored.
  // App also remounts this list when the signed-in user changes.
  const generation = useRef(0);
  const sentinel = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const gen = ++generation.current;
    setWords(null);
    setError(null);
    setMoreError(null);
    // Bug 16: bumping the generation abandons any in-flight Load more, so its own
    // setLoadingMore(false) will never run. The restart owns that flag now: reset it here.
    setLoadingMore(false);
    fetchWordsPage(null).then(
      (page) => {
        if (gen !== generation.current) return;
        setWords(page.rows);
        setTotal(page.total ?? page.rows.length);
        setCursor(page.cursor);
      },
      (err: Error) => gen === generation.current && setError(err.message),
    );
    return () => {
      generation.current++;
    };
  }, [version, attempt]);

  const loadMore = useCallback(() => {
    if (!cursor || loadingMore) return;
    const gen = generation.current;
    setLoadingMore(true);
    setMoreError(null);
    fetchWordsPage(cursor).then(
      (page) => {
        if (gen !== generation.current) return;
        setWords((shown) => mergePages(shown ?? [], page.rows));
        setCursor(page.cursor);
        setLoadingMore(false);
      },
      (err: Error) => {
        if (gen !== generation.current) return;
        setMoreError(err.message);
        setLoadingMore(false);
      },
    );
  }, [cursor, loadingMore]);

  // Load the next page when the bottom of the list scrolls into view (not after a failure:
  // that waits for Retry, so a broken connection isn't hammered while the bottom stays visible).
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !cursor || moreError || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore();
    }, { rootMargin: "200px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, [cursor, loadMore, moreError, words]);

  if (error) {
    return (
      <section className="panel center">
        <p className="error" role="alert">{error}</p>
        <button className="secondary" onClick={() => setAttempt((a) => a + 1)}>Retry</button>
      </section>
    );
  }
  if (!words) return <p className="muted" aria-busy="true">Loading your words…</p>;
  if (words.length === 0) {
    return (
      <section className="panel center">
        <h1>No words yet</h1>
        <p className="muted">Words you save from “Add word” appear here.</p>
      </section>
    );
  }

  return (
    <section className="list" aria-label="My words">
      <h1>My words <span className="muted count">{total}</span></h1>
      {words.map((w) => {
        const open = openId === w.id;
        const notes = [...w.notes].sort((a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind));
        const definition = w.notes.find((n) => n.kind === "definition")?.body;
        return (
          <article key={w.id} className="word">
            <button className="word-head" aria-expanded={open}
              onClick={() => setOpenId(open ? null : w.id)}>
              <span className="word-title">
                <strong>{w.surface_form}</strong>
                {w.lemma !== w.surface_form && <span className="muted"> · {w.lemma}</span>}
              </span>
              <span className="tag">{w.language}</span>
              {!open && definition && <span className="word-preview">{definition}</span>}
            </button>
            {open && (
              <dl className="word-notes">
                {notes.map((n, i) => (
                  <div key={i}>
                    <dt>{LABELS[n.kind] ?? n.kind}</dt>
                    <dd>{n.body}</dd>
                  </div>
                ))}
              </dl>
            )}
          </article>
        );
      })}
      {cursor && (
        <div ref={sentinel} className="load-more">
          {moreError && <p className="error" role="alert">{moreError}</p>}
          <button className="secondary" onClick={loadMore} disabled={loadingMore}>
            {loadingMore ? "Loading…" : moreError ? "Retry" : "Load more"}
          </button>
        </div>
      )}
    </section>
  );
}
