import { useEffect, useState } from "react";
import { CARD_FIELDS, supabase } from "./supabase";

type Note = { kind: string; body: string };
type Word = {
  id: string;
  surface_form: string;
  lemma: string;
  language: string;
  created_at: string;
  notes: Note[];
};

const LABELS: Record<string, string> = {
  ...Object.fromEntries(CARD_FIELDS.map(({ key, label }) => [key, label])),
  user: "My note",
};
const ORDER = [...CARD_FIELDS.map((f) => f.key as string), "user"];

/** `version` changes after every save; each change re-reads the list from the database. */
export default function Words({ version }: { version: number }) {
  const [words, setWords] = useState<Word[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    // Ignore a slow response once a newer read has started or this list has unmounted
    // (App remounts it when the signed-in user changes).
    let current = true;
    supabase
      .from("words")
      .select("id, surface_form, lemma, language, created_at, notes(kind, body)")
      .order("created_at", { ascending: false })
      .then(({ data, error }) => {
        if (!current) return;
        setError(error ? error.message : null);
        if (!error) setWords(data as Word[]);
      });
    return () => {
      current = false;
    };
  }, [version]);

  if (error) return <p className="error" role="alert">{error}</p>;
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
      <h1>My words <span className="muted count">{words.length}</span></h1>
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
    </section>
  );
}
