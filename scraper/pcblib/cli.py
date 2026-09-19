from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import db as dbm
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
def scrape(vendor: str, limit: int = 0, refresh: bool = False, only: str = "",
           dump: bool = False, reset: bool = False) -> None:
    """Scrape one vendor into data/library.sqlite (network responses are cached).
    --reset drops the vendor's existing rows first (use after parser changes)."""
    if vendor not in REGISTRY:
        raise typer.BadParameter(f"unknown vendor {vendor!r}; choose from {list(REGISTRY)}")
    adapter = REGISTRY[vendor](Fetcher(vendor=vendor, refresh=refresh))
    n_ok = n_skip = 0
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
                continue
            if c is None:
                n_skip += 1
                continue
            dbm.upsert_circuit(conn, c)
            conn.commit()  # short transactions so parallel vendor scrapes interleave
            n_ok += 1
            con.print(f"[green]{c.id}[/] {c.name!r} based_on={c.based_on!r} "
                      f"bom={len(c.bom)} sch_page={c.schematic_page} price={c.price}")
            if dump:
                con.print_json(json.dumps(c.to_dict(), default=str))
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


@app.command("import-transistors")
def import_transistors(dump_dir: str):
    """Load a MySQL dump of the transistor parameter database (parts, _assoc__part_props,
    _dict__prop_names .sql files) into data/transistors.sqlite and build the spec table."""
    from pathlib import Path
    from .transistors import build_specs, import_dump
    counts = import_dump(Path(dump_dir))
    con.print(f"imported {counts}")
    con.print(f"spec rows: {build_specs()}")
