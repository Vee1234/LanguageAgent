# Day 1 Bug Review

## Bug 1: Previous user's words stay on screen after switching users
**Source:** Qodo review (PR #2) · **Severity:** Medium: a privacy leak on a shared device, and a draft card can be saved under the wrong account.

### Reported issue
When the session changes directly from one signed-in user to another, the mounted My words list keeps showing the previous user's words. Qodo suggested keying the authenticated subtree by `session.user.id`.

### Root cause
`app/src/Words.tsx:40`: the fetch effect depends only on `[version]`, which changes on save, not on who is signed in. Combined with `app/src/App.tsx:46-65`, which renders the same `Words` and `AddWord` instances whatever the user (both deliberately kept mounted for the tabs), React keeps the components and their state when the user changes.

Failure scenario: user A is signed in with "maison" loaded. User B signs in in another tab, which updates this tab's session without passing through signed-out. This tab still shows "maison", never fetches B's words, and an unsaved card A generated in `AddWord` would be saved as **B's** word if Save is pressed.

Signing out first is not affected, because `<Login />` replaces the whole subtree. Row-level security in the database was never at fault: B could not *fetch* A's words; the browser simply kept the copy it already had.

### Solutions considered
1. **Key the authenticated subtree by `session.user.id`** (`App.tsx`): a different user remounts everything below, clearing all state and invalidating in-flight requests.
   - Pros: one line, and it covers `Words`, the `AddWord` draft and any future per-user component. Keying by user id rather than the session object avoids remounts on token refresh.
   - Cons: also resets harmless UI state, such as which word is expanded.
2. **Pass `userId` into `Words`, add it to the effect's dependencies and clear the list on change** (`Words.tsx`).
   - Pros: targeted; nothing else remounts.
   - Cons: only fixes the list. The `AddWord` draft can still be saved under the wrong user, and every future component must remember the same rule. It patches the symptom, not the root cause.
3. **A shared query cache (e.g. TanStack Query) with user-scoped keys, cleared on auth change.**
   - Pros: scales as the app grows.
   - Cons: a new dependency and a large refactor for a one-line problem.

No lessons were recorded before this review, so none applied.

### Chosen solution
Option 1. It fixes the root cause for every per-user component at once, including the draft-saved-as-wrong-user case that option 2 misses, with the smallest change.

### Biggest weakness
It only protects state that lives **inside** the keyed subtree. Anything outside it keeps the old user's data: `localStorage`, module-level variables, or a future header that shows user details. Nothing enforces this; it relies on future code being placed inside the keyed subtree.

### Implementation (TDD)
- **Red:** `App.test.tsx` › "replaces the previous user's words with the new user's words" and "ignores the previous user's response if it arrives after the switch" both failed with `expected [ { resolve: [Function] } ] to have a length of 2 but got 1`: no fetch happened for user B. (A first run failed for an unrelated reason, Node 25's built-in `localStorage` shadowing jsdom's; the test now stubs it.)
- **Green:** wrapped the authenticated subtree in `<Fragment key={session.user.id}>` in `app/src/App.tsx`. Result: `2 passed`; `tsc -b` clean; pytest `25 passed`.
- **Refactor:** updated the `Words.tsx` comment on the stale-response guard to cover unmounting; still `2 passed`.
- Added test-only dev dependencies: `@testing-library/react`, `@testing-library/dom`, `jsdom`. No Supabase changes.

### Lesson learned
> **L1:** Server-side security (RLS) only governs what is fetched; any client-side state holding user data must be scoped to the signed-in user's identity so that changing who is signed in always discards it.
