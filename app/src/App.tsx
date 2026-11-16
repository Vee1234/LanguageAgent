import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { configError, supabase } from "./supabase";
import Login from "./Login";
import AddWord from "./AddWord";
import Words from "./Words";

type Tab = "add" | "words";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("add");
  // Bumped after every save so My words re-reads from the database.
  const [wordsVersion, setWordsVersion] = useState(0);

  useEffect(() => {
    if (configError) return setLoading(false);
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  if (configError) {
    return (
      <main className="shell">
        <p className="error" role="alert">{configError}</p>
      </main>
    );
  }
  if (loading) return <main className="shell" aria-busy="true" />;

  return (
    <main className="shell">
      <header className="top">
        <span className="brand">Words</span>
        {session && (
          <button className="link" onClick={() => supabase.auth.signOut()}>
            Sign out
          </button>
        )}
      </header>
      {session ? (
        <>
          <nav className="tabs" aria-label="Sections">
            <button aria-current={tab === "add" ? "page" : undefined} onClick={() => setTab("add")}>
              Add word
            </button>
            <button aria-current={tab === "words" ? "page" : undefined} onClick={() => setTab("words")}>
              My words
            </button>
          </nav>
          {/* Both stay mounted, so My words is already up to date when you switch to it. */}
          <div hidden={tab !== "add"}>
            <AddWord
              onSaved={() => setWordsVersion((v) => v + 1)}
              onViewWords={() => setTab("words")}
            />
          </div>
          <div hidden={tab !== "words"}>
            <Words version={wordsVersion} />
          </div>
        </>
      ) : (
        <Login />
      )}
    </main>
  );
}
