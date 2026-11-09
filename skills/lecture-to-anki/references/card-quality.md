# Card quality rubric

## Accept if

1. **Atomic:** the learner can answer in ~5–30 seconds, or identify one concise method/idea without reproducing an entire derivation.
2. **Self-contained:** the question uniquely specifies context, object, and conditions.
3. **Accurate:** the source actually supports the answer; quantifiers and assumptions survive summarization.
4. **Useful:** remembering the answer helps solve a problem or explain an important concept.
5. **Nonredundant:** not an easy paraphrase of another card unless testing a genuinely different skill.

## Reject/revise if

- “Explain slide 17” or “What is important about graphs?” (depends on unavailable context).
- “List all 14 properties of …” (too much at once).
- A question with several unrelated subquestions.
- An algorithmic result stated without its assumptions, input model, or required complexity context.
- A copied exam problem requiring 10 minutes of calculation.
- An OCR-generated formula or diagram interpretation that has not been independently verified.
- Source only states a task and no available solution or theorem supports the proposed answer.
- Trivial one-off names/dates unconnected to learning objectives.

## Suggested card styles for CS/math courses

**Definitions:** “What does a graph being bipartite mean?” → “Its vertices admit a partition into two sets with no edges within either set.”

**Critical assumptions:** “Why can't ordinary Dijkstra be applied to graphs with negative edge weights?” → “Its greedy settled-distance choice relies on nonnegative edge weights.”

**Proof strategies:** “How can you show an undirected graph is bipartite?” → “Construct a 2-coloring (e.g., by BFS parity) or prove it has no odd cycle.”

**Algorithm invariants:** “What does BFS's queue order guarantee in an unweighted graph?” → “Vertices are first reached in nondecreasing distance (in edges) from the start vertex.”

**Comparisons:** “What key difference separates BFS from Dijkstra for shortest paths?” → “BFS handles unit-weight edges; Dijkstra handles general nonnegative edge weights.”

**Short exercise transfer:** “In a reduction proof, what two implications must be shown?” → “That a yes-instance maps to a yes-instance and a no-instance maps to a no-instance (plus polynomial-time computability).”

**Micro-examples:** “What is the out-degree of vertex v if it has three outgoing arcs (and no self-loops)?” → “3.” Use such cards only where examples clarify a meaningful concept.

**Cloze (sparingly):** “A tree with `n` vertices has {{c1::`n−1`}} edges.”

## Priority rubric

- `priority::high`: repeatedly examined/practiced or foundational for several later topics.
- `priority::medium`: part of learning objectives, sometimes practiced or examinable.
- `priority::low`: useful context, important only in one niche situation.

Never infer an exact probability of exam appearance from past exams.
