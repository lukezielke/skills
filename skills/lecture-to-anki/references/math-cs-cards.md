# Specialized mathematical and computer-science card design

Use `kind` in `cards.json` as a **semantic classification/tag**, not a new Anki note type. Most kinds should use `type: "basic"`; cloze is useful for a compact relation or formula.

| kind | Recall target | Good question pattern | Caution |
| --- | --- | --- | --- |
| `definition` | formal statement | "Under which condition is a graph bipartite?" | Don't drop quantifiers. |
| `theorem` | assertion with assumptions | "What does the max-flow min-cut theorem assert for finite capacitated networks?" | Test assumptions separately if important. |
| `assumption` | when a statement or tool applies | "Which restriction on edge weights is required by Dijkstra's correctness guarantee?" | Distinguish nonnegative vs positive. |
| `proof_idea` | one pivotal insight | "How does a BFS-parity coloring establish bipartiteness when there is no odd cycle?" | Avoid asking for a complete long proof. |
| `proof_step` | an inference/justification | "In the induction step for X, which invariant yields Y?" | Name the step and prior assumptions. |
| `counterexample` | minimal failing case | "Give a minimal counterexample to the claim that ..." | Verify it truly violates the claim. |
| `invariant` | algorithm invariant and consequence | "After BFS removes a vertex, what can be said about the next queue distances?" | Specify inputs/models. |
| `complexity` | cost + parameters/model | "What is the time bound for adjacency-list BFS with n vertices and m edges?" | State O(n+m), not just O(m). |
| `algorithm_trace` | one transition or execution step | "Given this heap/graph state, which vertex does Dijkstra settle next?" | Include tiny data/figure; not ten steps at once. |
| `reduction` | direction and correctness conditions | "To prove A ≤p B, which mapping and yes/no conditions must hold?" | Ensure arrow direction matches. |
| `application` | small representative problem | "With adjacency list X and start s, which nodes are BFS distance 2?" | Require enough problem data to answer. |
| `comparison` | essential difference/choice | "When is Bellman–Ford preferred over Dijkstra?" | Avoid superficial similarities. |
| `pitfall` | common incorrect shortcut | "Why is it invalid to cancel x in x·a ≡ x·b (mod m) without conditions?" | Explain exception/condition. |
| `worked_example` | one reusable method | "For this 3-edge graph, what is the MST cost and why?" | Use shortest meaningful example. |

## Formula and proof quality

- Use Anki MathJax `\( ... \)` or `\[ ... \]`; in JSON literal backslashes must be escaped (`"\\(n^2\\)"`).
- Cite all theorem preconditions, quantifiers, domain restrictions, asymptotic input-size models and hidden corner cases where relevant.
- For definitions, don't synonym-swap until rigor is lost.
- For *proof strategy* cards, focus on the key invariant/cut argument/inductive hypothesis rather than memorizing a paragraph.
- For *proof step* cards, the question must state enough mathematical context that the required inference is unique.
- Provide precise 1–4 line answers when possible; split anything larger into multiple notes.
- For diagrams, the learner must know exactly which vertex, state, edge or automaton is being referenced. Prefer a crop showing only the needed figure; never depend on a PDF page that is not visible in the card.
- If the source contains an unsolved exercise, extract its learning objective but do not treat a guessed answer as authoritative. Consult official solution or a verified theorem first.
- Examples should be small enough to answer mentally / on paper in under 1 minute unless the user explicitly requests longer exam-practice cards.

## Example notes

```json
{
  "id": "graphs.dijkstra.assumption",
  "type": "basic",
  "kind": "assumption",
  "front": "What condition on edge weights is sufficient for the standard Dijkstra algorithm to guarantee shortest paths?",
  "back": "Every edge has nonnegative weight.",
  "source_file": "lectures/shortest-paths.pdf",
  "source_location": "p. 6",
  "tags": ["topic::shortest_paths", "priority::high", "from::lecture"]
}
```

```json
{
  "id": "graphs.bfs.complexity",
  "type": "cloze",
  "kind": "complexity",
  "text": "Using adjacency lists, BFS on a graph with n vertices and m edges runs in {{c1::\\(O(n+m)\\)}} time.",
  "extra": "Each vertex and edge is processed only a constant number of times.",
  "source_file": "lectures/traversal.pdf",
  "source_location": "slide 12",
  "tags": ["topic::graphs", "priority::high", "from::lecture"]
}
```

### Balance by learning objective

For each major course topic, deliberately ask: What must I **state accurately**, what must I **explain**, what must I **execute**, and what common failure must I **recognize**? Never force one card of every kind: only write cards that the material supports.
