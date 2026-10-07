from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import db as dbm
from .enrich import enrich_from_schematic
from .fetch import Fetcher
from .vendors import REGISTRY, load_all

app = typer.Typer(help="Akashic scraper")
con = Console()
load_all()


@app.command()
def vendors() -> None:
    """List available vendor adapters."""
    for k in REGISTRY:
        con.print(k)


@app.command()
def scrape(vendor: str, limit: int = 0, refresh: bool = False, refresh_pages: bool = False, only: str = "",
           dump: bool = False, reset: bool = False) -> None:
    """Scrape one vendor into data/library.sqlite (network responses are cached).
    --refresh-pages re-fetches the vendor's pages (prices, stock, new boards) but keeps cached
    documents; --refresh re-fetches everything. --reset drops the vendor's existing rows first."""
    if vendor not in REGISTRY:
        raise typer.BadParameter(f"unknown vendor {vendor!r}; choose from {list(REGISTRY)}")
    adapter = REGISTRY[vendor](Fetcher(vendor=vendor, refresh=refresh, refresh_pages=refresh_pages))
    n_ok = n_skip = n_err = 0
    seen: set[str] = set()
    with dbm.connect() as conn:
        if reset and not only and not limit:
            conn.execute("DELETE FROM bom WHERE circuit_id IN (SELECT id FROM circuits WHERE vendor=?)", (vendor,))
            conn.execute("DELETE FROM circuits WHERE vendor=?", (vendor,))
            conn.commit()
        for i, target in enumerate(adapter.list_targets()):
            if only and only not in target:
                continue
            if limit and n_ok >= limit:
                break
            try:
                c = adapter.parse(target)
            except Exception as exc:  # keep going; report at the end
                con.print(f"[red]error[/] {target[:80]}: {exc!r}")
                n_err += 1
                continue
            if c is None:
                n_skip += 1
                continue
            try:
                enrich_from_schematic(c)
            except Exception as exc:  # the schematic is a bonus; never lose the board over it
                con.print(f"[yellow]schematic[/] {target[:60]}: {exc!r}")
            dbm.upsert_circuit(conn, c)
            conn.commit()  # short transactions so parallel vendor scrapes interleave
            n_ok += 1
            seen.add(c.id)
            con.print(f"[green]{c.id}[/] {c.name!r} based_on={c.based_on!r} "
                      f"bom={len(c.bom)} sch_page={c.schematic_page} price={c.price}")
            if dump:
                con.print_json(json.dumps(c.to_dict(), default=str))
        if not only and not limit and not n_err:
            # A full, clean run knows the vendor's whole listing: mark what is still listed and what is gone.
            from datetime import date
            listed, gone, applied = dbm.mark_listing(conn, vendor, seen, date.today().isoformat())
            conn.commit()
            if not applied:
                con.print(f"[red]{vendor}: found {listed} boards, far fewer than the library lists; not marking any delisted "
                          f"(check the scrape)[/]")
            elif gone:
                con.print(f"[yellow]{vendor}: {gone} boards no longer listed (kept, marked delisted)[/]")
    con.print(f"[bold]{vendor}[/]: {n_ok} circuits stored, {n_skip} targets skipped")


@app.command()
def stats() -> None:
    """Summarise the database."""
    with dbm.connect() as conn:
        t = Table("vendor", "circuits", "with BOM", "with schematic", "avg BOM rows")
        for r in conn.execute(
            """SELECT vendor, COUNT(*) n,
                      SUM(EXISTS(SELECT 1 FROM bom b WHERE b.circuit_id=c.id)) wb,
                      SUM(schematic_local != '') ws,
                      (SELECT AVG(cnt) FROM (SELECT COUNT(*) cnt FROM bom b JOIN circuits c2 ON c2.id=b.circuit_id WHERE c2.vendor=c.vendor GROUP BY b.circuit_id)) ab
               FROM circuits c GROUP BY vendor"""):
            t.add_row(r["vendor"], str(r["n"]), str(r["wb"]), str(r["ws"]), f"{(r['ab'] or 0):.1f}")
        con.print(t)


@app.command("attach-kicad")
def attach_kicad(circuit_id: str, kicad_sch: Path) -> None:
    """Attach a hand-drawn KiCad schematic fragment to a circuit (e.g. pedalpcb:pcb038).
    Copies it to app/static/kicad/<file_id>.kicad_sch and renders an SVG preview with kicad-cli."""
    import re
    import shutil
    import subprocess
    from .paths import REPO_ROOT
    if not kicad_sch.exists():
        raise typer.BadParameter(f"{kicad_sch} does not exist")
    file_id = re.sub(r"[^a-z0-9]+", "-", circuit_id.lower()).strip("-")
    out_dir = REPO_ROOT / "app" / "static" / "kicad"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{file_id}.kicad_sch"
    shutil.copyfile(kicad_sch, dst)
    kicad_cli = shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    tmp = out_dir / "_render"
    tmp.mkdir(exist_ok=True)
    r = subprocess.run([kicad_cli, "sch", "export", "svg", "--no-background-color", "--exclude-drawing-sheet",
                        "-o", str(tmp), str(dst)], capture_output=True, text=True)
    svgs = sorted(tmp.glob("*.svg"))
    if r.returncode != 0 or not svgs:
        con.print(f"[red]kicad-cli render failed[/]: {r.stderr.strip() or r.stdout.strip()}")
    else:
        shutil.move(str(svgs[0]), out_dir / f"{file_id}.svg")
        con.print(f"rendered {file_id}.svg")
    shutil.rmtree(tmp, ignore_errors=True)
    with dbm.connect() as conn:
        n = conn.execute("UPDATE circuits SET kicad_path=? WHERE id=?", (f"kicad/{file_id}.kicad_sch", circuit_id)).rowcount
    if not n:
        con.print(f"[yellow]no circuit with id {circuit_id!r} in the database; file copied anyway[/]")
    con.print(f"attached {dst.name} to {circuit_id}. Run `pcblib export` and rebuild the app.")


@app.command()
def export(images: bool = False) -> None:
    """Export the database to app/static/data/ as JSON for the web app.
    --images also bundles cached vendor schematic renders (local use only)."""
    from .export import run
    run(images=images)


if __name__ == "__main__":
    app()


@app.command()
def audit(show: int = 20, fail_on_added: bool = False) -> None:
    """Flag parts rows that do not look like valid parts and compare with the last run. Writes a
    filterable report to data/cache/audit/parts-audit.html. Run it after a rescrape and read the
    added flags before deploying: a parser change that makes rows worse shows up there.
    --fail-on-added exits with code 3 when the run added flags to boards that were already there
    (a parser regression); flags on boards new since the last run do not count. Used by
    scripts/refresh.sh."""
    from .audit import AUDIT_DIR, run
    r = run()
    con.print(f"audit run {r['run_at']}")
    con.print(f"{r['rows']:,} rows checked: [bold]{r['flags']:,}[/] flags on {r['boards']:,} boards "
              f"({r['severity'].get('high', 0)} high, {r['severity'].get('medium', 0)} medium, {r['severity'].get('low', 0)} low)")
    if r["previous"]:
        p = r["previous"]
        con.print(f"previous run{' ' + r['previous_run_at'] if r['previous_run_at'] else ''}: {p['flags']:,} flags on {p['boards']:,} boards; "
                  f"[green]{len(r['cleared'])} cleared[/], [{'red' if r['added'] else 'green'}]{len(r['added'])} added[/] on existing boards"
                  + (f", {len(r['added_new_boards'])} on boards new since then" if r.get("added_new_boards") else ""))
        changes = sorted((reason for reason in set(r["reasons"]) | set(r["reasons_before"]) if r["reasons"][reason] != r["reasons_before"][reason]),
                         key=lambda reason: r["reasons"][reason] - r["reasons_before"][reason])
        for reason in changes[:15]:
            con.print(f"  {r['reasons_before'][reason]:5} -> {r['reasons'][reason]:5}  {reason}")
        for f in sorted(r["added"], key=lambda f: {"high": 0, "medium": 1, "low": 2}[f["severity"]])[:show]:
            con.print(f"  [red]+[/] {f['severity']:6} {f['circuit']} {f['ref']} = {f['value']!r}: {f['reason']}")
    else:
        con.print("no previous run to compare with; this run is the baseline")
    con.print(f"report: {AUDIT_DIR / 'parts-audit.html'}")
    if fail_on_added and r["added"]:
        raise typer.Exit(code=3)  # the refresh routine stops here instead of deploying


@app.command("import-transistors")
def import_transistors(dump_dir: str):
    """Load a MySQL dump of the transistor parameter database (parts, _assoc__part_props,
    _dict__prop_names .sql files) into data/transistors.sqlite and build the spec table."""
    from pathlib import Path
    from .transistors import build_specs, import_dump
    counts = import_dump(Path(dump_dir))
    con.print(f"imported {counts}")
    con.print(f"spec rows: {build_specs()}")


@app.command()
def datasheets(add: list[str] = typer.Option(None, help="'CAT:PART=URL', a link checked in a browser"),
               host: list[Path] = typer.Option(None, help="An archived PDF of a discontinued part (named for the part), or a folder of them, to serve from the site"),
               force: bool = typer.Option(False, help="With --host: serve a sheet whose part number OCR could not find"),
               limit: int = 0) -> None:
    """Find manufacturer datasheet links for the parts cross-reference (run after export).
    Candidates on hosts that answer scripts (TI, Microchip, Vishay, Nisshinbo, Diodes) are fetched
    and kept when they are a PDF; a copy is cached in data/cache/datasheets/ for your own use and
    never exported. Candidates on hosts that block scripts (onsemi, Analog Devices, ST, Nexperia)
    are written to data/cache/datasheets/to-check.json for checking in a browser; record a good one
    with --add 'Q:2N3904=https://...'."""
    import hashlib
    import json
    import re
    import shutil
    from urllib.parse import urlparse
    from .datasheets import COVERED_BY, DISCONTINUED, FINDCHIPS, HOSTED, TABLE, candidates, is_selector, part_like, sheet_for, table
    from .datasheets import host as host_pdf
    from .fetch import Fetcher
    from .paths import CACHE_DIR, DATA_DIR
    known = table()
    for a in add or []:
        k, _, url = a.partition("=")
        known[k.strip()] = url.strip()
    parts = json.loads((DATA_DIR.parent / "app" / "static" / "data" / "parts.json").read_text())
    by_value = {p["value"]: p for p in parts}
    sheet_of = {v: k for k, vs in DISCONTINUED.items() for v in {k, *vs}}
    unlinked = {v for v, p in by_value.items() if p["category"] in ("IC", "Q", "D", "OPTO") and part_like(v)
                and not known.get(f'{p["category"]}:{v}', "").startswith("http")}
    served: dict[str, Path] = {}
    for src in [x for h in host or [] for x in (sorted(h.expanduser().glob("*.pdf")) if h.expanduser().is_dir() else [h.expanduser()])]:
        sheet = sheet_for(src.name)
        if not sheet:
            con.print(f"[yellow]skip[/] {src.name}: not a part in datasheets.DISCONTINUED")
            continue
        own = {sheet, *DISCONTINUED[sheet]}
        dst, why, mentioned = host_pdf(src, sheet, others=unlinked - own, force=force)
        if not dst:
            con.print(f"[red]refused[/] {src.name}: {why}")
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        same = served.get(digest)
        served.setdefault(digest, dst)
        if same and same != dst:  # one download saved under two names (AC128 and AC176 from one catalog): serve it once
            dst.unlink()
            dst, why = same, f"{why}, same file as {same.name}"
        for v in own & by_value.keys():
            known[f'{by_value[v]["category"]}:{v}'] = f"datasheets/{dst.name}"
        con.print(f"[green]hosted[/] {sheet} <- {src.name} ({why}, {dst.stat().st_size // 1024} KB)")
        for v in sorted(mentioned):
            key = f'{by_value[v]["category"]}:{v}'
            have = known.get(key, "")
            better = not have or is_selector(have) and not is_selector(f"datasheets/{dst.name}")
            if v in sheet_of and not (HOSTED / f"{sheet_of[v]}.pdf").exists() and better:  # a sheet of its own wins, a datasheet beats a table
                known[key] = f"datasheets/{dst.name}"
                con.print(f"    also covers {key}")
            elif v not in sheet_of:
                con.print(f"    [dim]mentions {key} (not discontinued; not linked)[/]")
    for f, covered in COVERED_BY.items():
        link = f"datasheets/{f}.pdf"
        if not (HOSTED / f"{f}.pdf").exists():
            continue
        for v in covered:
            have = known.get(f'{by_value[v]["category"]}:{v}', "") if v in by_value else "x"
            own = v in sheet_of and (HOSTED / f"{sheet_of[v]}.pdf").exists()
            if v in by_value and not own and (not have or is_selector(have) and not is_selector(link)):
                known[f'{by_value[v]["category"]}:{v}'] = link
                con.print(f"covers {v} <- {f}.pdf")
    open_hosts = {"www.ti.com", "ww1.microchip.com", "www.vishay.com", "www.nisshinbo-microdevices.co.jp", "www.diodes.com", "electricdruid.net"}
    out = CACHE_DIR / "datasheets"
    out.mkdir(parents=True, exist_ok=True)
    f = Fetcher(vendor="datasheets", min_interval=2.0)
    to_check: dict[str, list[str]] = {}
    tried = 0
    for p in sorted(parts, key=lambda p: -p["count"]):
        key = f'{p["category"]}:{p["value"]}'
        if p["category"] not in ("IC", "Q", "D", "OPTO") or key in known:
            continue
        if limit and tried >= limit:
            break
        tried += 1
        blocked = []
        for url in candidates(p["category"], p["value"]):
            if urlparse(url).netloc not in open_hosts:
                blocked.append(url)
                continue
            path = f.get_file(url, ".pdf")
            if path and path.read_bytes()[:5] == b"%PDF-":
                known[key] = url
                shutil.copyfile(path, out / f'{p["slug"]}.pdf')
                con.print(f"[green]{key}[/] {url}")
                break
        else:
            if blocked:
                to_check[key] = blocked
    TABLE.write_text(json.dumps(dict(sorted(known.items())), indent=1) + "\n")
    (out / "to-check.json").write_text(json.dumps(to_check, indent=1))
    def status(k: str) -> str:
        links = [known.get(f'{by_value[v]["category"]}:{v}', "") for v in {k, *DISCONTINUED[k]} if v in by_value]
        return "done" if any(lk and not is_selector(lk) for lk in links) else "selector" if any(links) else "todo"

    uses = {k: sum(by_value[v]["count"] for v in {k, *vs} if v in by_value) for k, vs in DISCONTINUED.items()}
    todo = sorted(((uses[k], k) for k in DISCONTINUED if status(k) == "todo"), reverse=True)
    tables = sorted(((uses[k], k) for k in DISCONTINUED if status(k) == "selector"), reverse=True)

    def table_html(items) -> str:
        rows = "".join(f'<tr><td>{n}</td><td><a href="{FINDCHIPS.format(k)}" target="_blank">{k}</a></td><td><code>{k}.pdf</code></td></tr>' for n, k in items)
        return f"<table><tr><th>Uses</th><th>Part</th><th>Save as</th></tr>{rows}</table>"

    (out / "discontinued.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Discontinued datasheets</title><style>body{font:14px system-ui;margin:2em}"
        "td{padding:2px 12px}h2{margin-top:2em}</style><h1>Discontinued datasheets to download</h1><p>Open each on Findchips, download the archived "
        "sheet, save it as the name shown into one folder, then run <code>pcblib datasheets --host &lt;folder&gt;</code>.</p>"
        + table_html(todo)
        + "<h2>Has a selector sheet, not a datasheet</h2><p>Served from a row in a maker's selector table or catalog for now; "
        "a full datasheet saved under the same name replaces it.</p>" + table_html(tables))
    con.print(f"{len(known)} parts with a datasheet; {len(to_check)} to check in a browser -> {out / 'to-check.json'}; "
              f"{len(todo)} discontinued sheets to download and {len(tables)} with only a selector table -> {out / 'discontinued.html'}")
