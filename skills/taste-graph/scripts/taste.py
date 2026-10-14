#!/usr/bin/env python3
"""Personal taste graph in an Obsidian vault, for an AI agent that recommends what to watch, read, play or eat.

The agent interprets what the user says; this script keeps the notes consistent.

Notes live in one vault folder (set with `init`):
  <profile>.md   free-form profile written by the user: services, devices, moments, dislikes, rules
  works/         one note per work (movie, series, book, podcast, channel, music, game, food, other)
  people/        directors, authors, creators linked from 2+ works
  themes/        genres, moods and topics linked from 2+ works
Works link to people and themes through frontmatter properties ("[[Name]]"), so Obsidian's graph
and backlinks show the connections. The user may edit any note by hand.

Agent state lives in $TASTE_HOME (default ~/.hermes/taste): config.json and recs.jsonl.

Commands (JSON arguments are single-quoted strings):
  init --dir PATH [--locale pt-BR|en] [--hub-min N]
  add '<json object or list>'     create or update works; lists merge; "note" is appended with the date
  find <words...>                 works, people and themes matching the words
  show <title>                    print one work note
  index [--type T] [--status S]   compact list of works plus people and themes with counts
  hubs                            create missing people/theme notes (after hand edits)
  profile                         print the profile note
  rec '<json>' | recs [--days N]  log recommendations given, list recent ones
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

TYPES = ("movie", "series", "book", "podcast", "channel", "music", "game", "food", "other")
STATUSES = ("favorite", "done", "current", "want", "dropped")
LISTS = ("creators", "themes", "aliases")
FIELDS = ("type", "title", "year", "status", "rating", "creators", "themes", "where", "aliases")
BAD_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]]')

TEXT = {
    "pt-BR": {
        "dirs": {"works": "obras", "people": "pessoas", "themes": "temas"},
        "profile": "perfil", "notes": "Notas",
        "types": {"movie": "filme", "series": "série", "book": "livro", "podcast": "podcast", "channel": "canal",
                  "music": "música", "game": "jogo", "food": "comida", "other": "outro"},
        "statuses": {"favorite": "favorito", "done": "visto", "current": "em andamento", "want": "quero",
                     "dropped": "abandonado"},
        "created": "✅ Nova nota: {title} ({type})", "updated": "✅ Atualizado: {title} ({type})",
        "hub": "🔗 {name} agora liga {n} obras: nota criada", "no_hubs": "Nenhuma nota nova de pessoa ou tema.",
        "people": "Pessoas", "themes": "Temas", "works": "Obras", "none": "Nada encontrado.",
        "rec_logged": "📝 Recomendações registradas: {titles}", "no_recs": "Nenhuma recomendação nos últimos {days} dias.",
        "profile_body": "# Perfil de gostos\n\nEscreva aqui, com suas palavras, o que o agente deve saber:\n\n"
                        "## Onde assisto e jogo\n- \n\n## Momentos\n- \n\n## Não gosto\n- \n\n## Regras\n- \n",
    },
    "en": {
        "dirs": {"works": "works", "people": "people", "themes": "themes"},
        "profile": "profile", "notes": "Notes",
        "types": {t: t for t in TYPES},
        "statuses": {s: s for s in STATUSES},
        "created": "✅ New note: {title} ({type})", "updated": "✅ Updated: {title} ({type})",
        "hub": "🔗 {name} now links {n} works: note created", "no_hubs": "No new people or theme notes.",
        "people": "People", "themes": "Themes", "works": "Works", "none": "Nothing found.",
        "rec_logged": "📝 Recommendations logged: {titles}", "no_recs": "No recommendations in the last {days} days.",
        "profile_body": "# Taste profile\n\nWrite here, in your own words, what the agent should know:\n\n"
                        "## Where I watch and play\n- \n\n## Moments\n- \n\n## Dislikes\n- \n\n## Rules\n- \n",
    },
}


class UserError(Exception):
    pass


# ---------- frontmatter ----------

def _scalar(raw: str):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1].replace('\\"', '"') if raw[0] == '"' else raw[1:-1].replace("''", "'")
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def _flow_list(raw: str) -> list:
    inner, items, cur, quote = raw.strip()[1:-1], [], "", None
    for ch in inner:
        if quote:
            cur += ch
            quote = None if ch == quote else quote
        elif ch in "\"'":
            cur, quote = cur + ch, ch
        elif ch == ",":
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    return [_scalar(i) for i in items if i.strip()]


def parse_note(text_: str) -> tuple[dict, str]:
    """Split a note into (frontmatter dict, body). Handles the YAML subset Obsidian writes."""
    if not text_.startswith("---\n"):
        return {}, text_
    end = text_.find("\n---", 4)
    if end < 0:
        return {}, text_
    meta, key = {}, None
    for line in text_[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"\s*-\s+(.*)", line)
        if item and key:
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(_scalar(item.group(1)))
            continue
        m = re.match(r"([A-Za-z_][\w-]*):\s*(.*)", line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        meta[key] = _flow_list(raw) if raw.startswith("[") and raw.endswith("]") else (_scalar(raw) if raw else None)
    body = text_[end + 4:]
    return meta, body[1:] if body.startswith("\n") else body


def _quote(v) -> str:
    if isinstance(v, int):
        return str(v)
    return '"' + str(v).replace('"', '\\"') + '"'


def dump_note(meta: dict, body: str) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}:" if v else f"{k}: []")
            lines += [f"  - {_quote(i)}" for i in v]
        elif v is not None and v != "":
            lines.append(f"{k}: {_quote(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


# ---------- helpers ----------

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def filename(name: str) -> str:
    out = " ".join(BAD_CHARS.sub("-", name).split()).strip(". ")
    if not out:
        raise UserError(f"Invalid name: {name!r}")
    return out


def link(name: str) -> str:
    f = filename(name)
    return f"[[{f}]]" if f == name else f"[[{f}|{name}]]"


def unlink(value) -> str:
    m = re.fullmatch(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", str(value).strip())
    return (m.group(2) or m.group(1)) if m else str(value).strip()


def as_list(value) -> list:
    if value in (None, ""):
        return []
    return value if isinstance(value, list) else [value]


def parse_json(raw: str, what: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UserError(f"Invalid JSON for {what}: {exc}") from None


def today(cfg: dict) -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(cfg.get("timezone", "UTC"))).date().isoformat()
    except Exception:
        return date.today().isoformat()


# ---------- vault ----------

class Vault:
    def __init__(self, home: Path):
        self.home = home
        self.config_path = home / "config.json"
        self.recs_path = home / "recs.jsonl"
        self._cfg = None

    @property
    def cfg(self) -> dict:
        if self._cfg is None:
            if not self.config_path.exists():
                raise UserError(f"Not set up yet. Run: init --dir <vault folder> (home: {self.home})")
            self._cfg = json.loads(self.config_path.read_text())
        return self._cfg

    @property
    def t(self) -> dict:
        return TEXT.get(self.cfg.get("locale", "en"), TEXT["en"])

    @property
    def root(self) -> Path:
        return Path(self.cfg["dir"]).expanduser()

    def folder(self, kind: str) -> Path:
        return self.root / self.t["dirs"][kind]

    def profile_path(self) -> Path:
        return self.root / f"{self.t['profile']}.md"

    def works(self) -> list[tuple[Path, dict, str]]:
        out = []
        folder = self.folder("works")
        for path in sorted(folder.glob("*.md")) if folder.exists() else []:
            meta, body = parse_note(path.read_text())
            meta.setdefault("title", path.stem)
            out.append((path, meta, body))
        return out

    def write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content)
        os.replace(tmp, path)


def label(v: Vault, kind: str, value) -> str:
    return v.t[kind].get(value, str(value)) if value else ""


def matches(meta: dict, path: Path, title: str) -> bool:
    want = normalize(title)
    names = [meta.get("title", ""), path.stem, *as_list(meta.get("aliases"))]
    return any(normalize(n) == want for n in names if n)


def locate(v: Vault, title: str, type_: str | None) -> tuple[Path, dict, str] | None:
    hits = [w for w in v.works() if matches(w[1], w[0], title)]
    if type_:
        hits = [w for w in hits if w[1].get("type") == type_]
    if len(hits) > 1:
        kinds = ", ".join(sorted({str(w[1].get("type")) for w in hits}))
        raise UserError(f"'{title}' matches several works ({kinds}); pass \"type\".")
    return hits[0] if hits else None


def validate(item: dict) -> None:
    if not isinstance(item, dict) or not str(item.get("title", "")).strip():
        raise UserError("Each work needs a \"title\".")
    unknown = set(item) - set(FIELDS) - {"note", "date"}
    if unknown:
        raise UserError(f"Unknown fields: {', '.join(sorted(unknown))}. Allowed: {', '.join(FIELDS)}, note, date.")
    if item.get("type") and item["type"] not in TYPES:
        raise UserError(f"type must be one of: {', '.join(TYPES)}")
    if item.get("status") and item["status"] not in STATUSES:
        raise UserError(f"status must be one of: {', '.join(STATUSES)}")
    if item.get("rating") is not None and not (isinstance(item["rating"], int) and 1 <= item["rating"] <= 5):
        raise UserError("rating must be an integer from 1 to 5.")
    if item.get("year") is not None and not isinstance(item["year"], int):
        raise UserError("year must be an integer.")
    if item.get("date"):
        date.fromisoformat(item["date"])


def append_note(v: Vault, body: str, day: str, note: str) -> str:
    heading = f"## {v.t['notes']}"
    entry = f"- {day} · {' '.join(note.split())}"
    lines = body.rstrip("\n").split("\n") if body.strip() else []
    if heading not in lines:
        return "\n".join([*lines, "", heading, entry]).lstrip("\n") + "\n"
    i = lines.index(heading) + 1
    while i < len(lines) and not lines[i].startswith("## "):
        i += 1
    while i > 0 and not lines[i - 1].strip():
        i -= 1
    lines.insert(i, entry)
    return "\n".join(lines) + "\n"


def upsert(v: Vault, item: dict) -> tuple[str, Path]:
    validate(item)
    title = " ".join(str(item["title"]).split())
    found = locate(v, title, item.get("type"))
    if found:
        path, meta, body = found
        created = False
    else:
        if not item.get("type"):
            raise UserError(f"'{title}' is new; pass \"type\" ({', '.join(TYPES)}).")
        path = v.folder("works") / f"{filename(title)}.md"
        if path.exists():
            path = path.with_name(f"{filename(title)} ({label(v, 'types', item['type'])}).md")
        meta, body, created = {"type": item["type"], "title": title}, f"# {title}\n", True

    for key in ("type", "year", "status", "rating", "where"):
        if item.get(key) not in (None, ""):
            meta[key] = item[key]
    for key in LISTS:
        if key in item:
            current = as_list(meta.get(key))
            seen = {normalize(unlink(x)) for x in current}
            for name in as_list(item[key]):
                name = " ".join(str(unlink(name)).split())
                if name and normalize(name) not in seen:
                    current.append(name if key == "aliases" else link(name))
                    seen.add(normalize(name))
            meta[key] = current
    day = item.get("date") or today(v.cfg)
    meta["updated"] = day
    ordered = {k: meta[k] for k in (*FIELDS, "updated") if k in meta}
    ordered.update({k: val for k, val in meta.items() if k not in ordered})
    if item.get("note"):
        body = append_note(v, body, day, str(item["note"]))
    v.write(path, dump_note(ordered, body))
    msg = v.t["created" if created else "updated"].format(title=ordered["title"], type=label(v, "types", ordered["type"]))
    extras = [label(v, "statuses", ordered.get("status")), f"★{ordered['rating']}" if ordered.get("rating") else ""]
    return " · ".join([msg, *[e for e in extras if e]]), path


def hub_counts(v: Vault) -> dict[str, Counter]:
    counts = {"people": Counter(), "themes": Counter()}
    for _, meta, _ in v.works():
        for kind, key in (("people", "creators"), ("themes", "themes")):
            for name in {unlink(x) for x in as_list(meta.get(key))}:
                counts[kind][name] += 1
    return counts


def ensure_hubs(v: Vault) -> list[str]:
    created, minimum = [], int(v.cfg.get("hub_min", 2))
    existing = {normalize(p.stem) for p in v.root.rglob("*.md")} if v.root.exists() else set()
    for kind, counter in hub_counts(v).items():
        for name, n in sorted(counter.items()):
            if n < minimum or normalize(filename(name)) in existing:
                continue
            path = v.folder(kind) / f"{filename(name)}.md"
            v.write(path, dump_note({"kind": "person" if kind == "people" else "theme"}, f"# {name}\n"))
            existing.add(normalize(filename(name)))
            created.append(v.t["hub"].format(name=name, n=n))
    return created


# ---------- commands ----------

def cmd_init(v: Vault, args) -> str:
    if args.locale not in TEXT:
        raise UserError(f"locale must be one of: {', '.join(TEXT)}")
    cfg = json.loads(v.config_path.read_text()) if v.config_path.exists() else {}
    cfg.update({"dir": str(Path(args.dir).expanduser()), "locale": args.locale, "hub_min": args.hub_min})
    if args.timezone:
        cfg["timezone"] = args.timezone
    v.home.mkdir(parents=True, exist_ok=True)
    v.config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    v._cfg = cfg
    for kind in ("works", "people", "themes"):
        v.folder(kind).mkdir(parents=True, exist_ok=True)
    if not v.profile_path().exists():
        v.write(v.profile_path(), v.t["profile_body"])
    return f"Ready: {v.root} (profile: {v.profile_path().name})"


def cmd_add(v: Vault, args) -> str:
    payload = parse_json(args.json, "add")
    items = payload if isinstance(payload, list) else [payload]
    lines = [upsert(v, item)[0] for item in items]
    return "\n".join([*lines, *ensure_hubs(v)])


def work_line(v: Vault, meta: dict) -> str:
    head = f"{meta['title']}"
    kind = label(v, "types", meta.get("type")) + (f" {meta['year']}" if meta.get("year") else "")
    status = " ".join(x for x in (f"★{meta['rating']}" if meta.get("rating") else "",
                                  label(v, "statuses", meta.get("status"))) if x)
    people = ", ".join(unlink(x) for x in as_list(meta.get("creators")))
    themes = ", ".join(unlink(x) for x in as_list(meta.get("themes")))
    parts = [head, kind, status, people, themes, meta.get("where") or ""]
    return " · ".join(p for p in parts if p)


def cmd_find(v: Vault, args) -> str:
    words = normalize(" ".join(args.words)).split()
    out = []
    for _, meta, _ in v.works():
        hay = normalize(" ".join([work_line(v, meta), *map(str, as_list(meta.get("aliases")))]))
        if all(w in hay for w in words):
            out.append(work_line(v, meta))
    return "\n".join(out[: args.limit]) if out else v.t["none"]


def cmd_show(v: Vault, args) -> str:
    found = locate(v, " ".join(args.title), args.type)
    if not found:
        raise UserError(v.t["none"])
    return found[0].read_text().rstrip()


def cmd_index(v: Vault, args) -> str:
    works = [m for _, m, _ in v.works()
             if (not args.type or m.get("type") == args.type) and (not args.status or m.get("status") == args.status)]
    order = {s: i for i, s in enumerate(STATUSES)}
    works.sort(key=lambda m: (str(m.get("type")), order.get(m.get("status"), 9), normalize(m["title"])))
    lines = [f"## {v.t['works']} ({len(works)})", *[work_line(v, m) for m in works]]
    counts = hub_counts(v)
    for kind in ("people", "themes"):
        counter = counts[kind]
        top = [f"{n} ({c})" for n, c in counter.most_common() if c >= 2]
        if top:
            lines += ["", f"## {v.t[kind]}", ", ".join(top)]
    return "\n".join(lines)


def cmd_hubs(v: Vault, args) -> str:
    return "\n".join(ensure_hubs(v)) or v.t["no_hubs"]


def cmd_profile(v: Vault, args) -> str:
    path = v.profile_path()
    return path.read_text().rstrip() if path.exists() else v.t["none"]


def cmd_rec(v: Vault, args) -> str:
    payload = parse_json(args.json, "rec")
    picks = payload.get("picks") if isinstance(payload, dict) else None
    if not picks or not all(isinstance(p, str) and p.strip() for p in picks):
        raise UserError('rec needs {"request": "...", "picks": ["Title", ...]}')
    entry = {"date": payload.get("date") or today(v.cfg), "request": str(payload.get("request", "")),
             "picks": [p.strip() for p in picks]}
    v.home.mkdir(parents=True, exist_ok=True)
    with v.recs_path.open("a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return v.t["rec_logged"].format(titles=", ".join(entry["picks"]))


def cmd_recs(v: Vault, args) -> str:
    since = (date.fromisoformat(today(v.cfg)) - timedelta(days=args.days)).isoformat()
    rows = []
    if v.recs_path.exists():
        for line in v.recs_path.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                if e["date"] >= since:
                    rows.append(f"{e['date']} · {e['request']} → {', '.join(e['picks'])}")
    return "\n".join(rows) or v.t["no_recs"].format(days=args.days)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--home", default=os.environ.get("TASTE_HOME") or str(Path.home() / ".hermes" / "taste"))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("--dir", required=True)
    s.add_argument("--locale", default="en")
    s.add_argument("--timezone")
    s.add_argument("--hub-min", type=int, default=2)

    sub.add_parser("add").add_argument("json")

    s = sub.add_parser("find")
    s.add_argument("words", nargs="+")
    s.add_argument("--limit", type=int, default=15)

    s = sub.add_parser("show")
    s.add_argument("title", nargs="+")
    s.add_argument("--type", choices=TYPES)

    s = sub.add_parser("index")
    s.add_argument("--type", choices=TYPES)
    s.add_argument("--status", choices=STATUSES)

    sub.add_parser("hubs")
    sub.add_parser("profile")
    sub.add_parser("rec").add_argument("json")
    sub.add_parser("recs").add_argument("--days", type=int, default=60)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    v = Vault(Path(args.home).expanduser())
    handlers = {"init": cmd_init, "add": cmd_add, "find": cmd_find, "show": cmd_show, "index": cmd_index,
                "hubs": cmd_hubs, "profile": cmd_profile, "rec": cmd_rec, "recs": cmd_recs}
    try:
        print(handlers[args.cmd](v, args))
    except (UserError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
