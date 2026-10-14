---
name: taste-graph
description: "Personal taste graph in Obsidian plus recommendations by mood. Use when the user tells you about something they watched, read, listened to, played or ate ('vi o filme X ontem, me prendeu', 'tô lendo Y, aprendi Z'), wants to save something for later, or asks what to watch, read, hear, play or eat now ('tô entediado, quero um filme pra me animar', 'vou pedalar 1h, sugere algo')."
version: 1.0.0
author: Lucas Rotsen
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [recommendations, movies, series, books, podcasts, music, games, food, obsidian, taste, mood]
    category: media
    prerequisites:
      commands: [python3]
---

# Taste graph

You keep the user's taste as linked notes in their Obsidian vault and use them to recommend what fits right
now. **You interpret; the script writes the notes.** Never create or edit work notes by hand.

Script (Python 3.10+, stdlib only), called `taste` below:

```
python3 ~/.hermes/skills/media/taste-graph/scripts/taste.py <command>
```

If that file does not exist, use `${HERMES_SKILL_DIR}/scripts/taste.py`. Settings live in `$TASTE_HOME`
(default `~/.hermes/taste`).

| Need | Command |
|---|---|
| Set up | `taste init --dir <vault>/taste --locale pt-BR --timezone America/Sao_Paulo` |
| Profile (their words) | `taste profile` |
| Everything, compact | `taste index` · `taste index --type movie` · `taste index --status want` |
| Search | `taste find terror sobrenatural` |
| One note | `taste show <title>` |
| Save or update works | `taste add '<json object or list>'` |
| Recommendations given | `taste rec '{"request":"…","picks":["…"]}'` · `taste recs --days 90` |
| People/theme notes after hand edits | `taste hubs` |

Types: `movie series book podcast channel music game food other`.
Status: `favorite` (all-time), `done` (seen/read/played), `current` (in progress), `want` (their list), `dropped`.

`add` JSON (only `title` is required to update; new works also need `type`):

```json
{"type": "movie", "title": "Hereditário", "year": 2018, "status": "done", "rating": 5,
 "creators": ["Ari Aster"], "themes": ["terror sobrenatural", "luto"], "where": "Prime Video",
 "aliases": ["Hereditary"], "note": "Não dava nada, mas me prendeu do começo ao fim.", "date": "2026-10-13"}
```

Lists (`creators`, `themes`, `aliases`) merge with what is there. `note` is appended to the note's dated log.
A person or theme gets its own note once 2 works link to it, so the graph grows on its own.

## First use

If `taste profile` says it is not set up, ask where their vault is and create the folder with `init`. Then,
in ONE message, ask for: all-time favorites of each kind they care about, streaming services and devices, the
moments they want suggestions for (e.g. "bike at home, TV, 45–60 min"), what they cannot stand, and any rules
("alternate fiction and non-fiction"). Write the profile note from their answers (it is theirs: keep their
words), then save the favorites with one `taste add` list.

## When they tell you about something

"Vi X", "terminei Y", "tô lendo Z e aprendi…", "joguei…", "comi um … incrível", "quero ver …":

1. `taste find <title>` to reuse an existing note's exact title.
2. `taste add` with what they said:
   - `status`: `current` while in progress, `done` when finished, `want` for "quero ver/ler", `dropped` if they gave up.
     Use `favorite` only when they say it is one of their favorites.
   - `rating` only if they gave one or said something unmistakable ("obra-prima" = 5). Never ask for it.
   - `note`: their reaction and what they learned, close to their words, one or two sentences. No embellishment.
   - `creators` and 1–3 `themes`: reuse theme names from `taste index` when they fit, so links connect.
     New themes are fine when nothing fits. Themes are genres, moods, topics or styles, in their language.
3. Reply with the script's lines, plus at most one short line of conversation if they want to talk about it.

## When they ask what to watch, read, hear, play or eat

1. Read `taste profile`, `taste index` and `taste recs --days 90`.
2. Understand the moment: mood, time available, place and device (match a moment in their profile, e.g. the
   bike), alone or with someone. Ask one question only if the type of content is truly unclear.
3. Pick 2–3 options:
   - **Aposta segura:** close to their favorites (same people, overlapping themes).
   - **Surpresa:** one step away (a neighbouring theme, a creator they would likely like, a classic they have
     not met).
   - Prefer their `want` list when something there fits. Avoid `done`/`dropped` works and recent `recs`, unless
     they ask for a rewatch or comfort content (a favorite series, a playlist, a dish).
   - Respect the time available, their dislikes and their rules.
4. Reply in ≤ 8 lines, per option: title (year) · type · duration · where. Then one line on why it fits now,
   tied to their taste ("o clima de Os Goonies, mas …"). Where to watch comes from your knowledge, limited to the
   services in their profile; mark it "provável", since catalogues change. No spoilers.
5. Log the picks with `taste rec`. If they choose one, `taste add` it with `status: current` or `want`.

Food: suggest from their `food` works and themes. If a calorie or macro tracker skill is installed and they
ask for something that fits their day, check it with that skill before suggesting.

## Profile changes

When you notice a pattern ("3 slow documentaries dropped"), propose a profile change in one line. Edit only the
profile note, and only after they say yes.

## Rules

- Read only the profile, `taste index` and the notes in this folder. Never read the rest of the vault for this.
- Say something was saved only after the script printed its ✅ line.
- Never invent taste: everything in the notes comes from what they said.
- No moralizing about what they like, eat or skip.
- Their notes are personal: never send them anywhere they did not ask for.
