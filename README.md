# hermes-taste-graph

A taste graph and recommendation skill for [Hermes Agent](https://github.com/NousResearch/hermes-agent) (and
any agent that reads `SKILL.md` skills). Tell your agent what you watched, read, heard, played or ate, in your
own words; it keeps linked notes in your Obsidian vault. Ask "what should I watch now?" and it answers from
those notes, your mood and the time you have.

```
you:   watched Hereditary yesterday, wasn't expecting much, it gripped me from start to finish
agent: ✅ New note: Hereditary (movie) · done · ★5
       🔗 supernatural horror now links 2 works: note created

you:   bored, 1h on the exercise bike, something to cheer me up
agent: Safe bet: … · Surprise: … (each with duration, where to watch and why it fits now)
```

## Design

- **Obsidian-native.** One note per work; directors, authors and themes are links in the note's properties,
  so the graph view and backlinks show your taste. A person or theme gets its own note once two works share
  it. Edit any note by hand: the script keeps your text and properties.
- **The model interprets, the script writes.** Notes stay consistent (merged lists, dated log entries) no
  matter how you phrase things.
- **Small context.** For recommendations the agent reads your profile and a compact index of the folder, not
  your whole vault.
- **Personal and private.** Your profile and notes live in your vault; the agent's settings and the log of
  recommendations live in `$TASTE_HOME` (default `~/.hermes/taste`). Nothing personal is in this repo.

Kinds: movie, series, book, podcast, channel, music, game, food, other.
Status: favorite, done, current, want (your list), dropped.

## Install (Hermes)

```bash
hermes skills install LucasRotsen/hermes-taste-graph/skills/taste-graph --category media
```

Start a new chat (`/new` on Telegram, since gateway sessions load skills only when they start) and say
"set up my taste graph". The agent asks where your vault is and what you love, and writes your profile.

## Command line

```bash
S=skills/taste-graph/scripts/taste.py
python3 $S init --dir ~/vault/taste --locale en
python3 $S add '{"type":"movie","title":"Hereditary","year":2018,"status":"done","rating":5,"creators":["Ari Aster"],"themes":["supernatural horror"],"note":"Gripped me."}'
python3 $S index
python3 $S find horror
python3 $S rec '{"request":"bored, 1h bike","picks":["The Goonies"]}'
```

Run `python3 $S --help` for every command and see [SKILL.md](skills/taste-graph/SKILL.md) for the agent workflow.

## Português

Skill de grafo de gostos e recomendações para o Hermes. Você conta o que viu, leu, ouviu, jogou ou comeu, do seu
jeito ("vi Hereditário ontem, não dava nada e me prendeu"), e o agente mantém notas ligadas no seu Obsidian.
Pergunte "tô entediado, quero um filme pra me animar" e ele recomenda a partir das notas, do seu humor e do tempo
que você tem.

1. Instale: `hermes skills install LucasRotsen/hermes-taste-graph/skills/taste-graph --category media`
2. No Telegram, mande `/new`.
3. Diga "quero montar meu grafo de gostos". O agente pergunta onde fica o vault e o que você ama, e escreve seu
   perfil (`perfil.md`) e as notas em `obras/`, `pessoas/` e `temas/`.

O "onde assistir" vem do conhecimento do modelo e aparece como provável: catálogos de streaming mudam todo mês.

## License

[MIT](LICENSE).
