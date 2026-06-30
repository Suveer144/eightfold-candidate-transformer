from __future__ import annotations
import json
import sys
import click
from .pipeline import run_pipeline


@click.group()
@click.version_option("0.1.0", prog_name="candidate-transformer")
def cli():
    """Candidate Data Transformer — normalizes multi-source candidate profiles into a canonical schema."""


@cli.command()
@click.option(
    "--source", "-s",
    multiple=True,
    metavar="TYPE:PATH",
    required=True,
    help="Source in TYPE:PATH format (e.g. crm:data/crm.csv). Repeatable.",
)
@click.option(
    "--config", "-c",
    default=None,
    metavar="PATH",
    help="JSON or YAML runtime config (reshapes output). Omit for the full canonical schema.",
)
@click.option(
    "--output", "-o",
    default=None,
    metavar="PATH",
    help="Write JSON to this file instead of stdout.",
)
@click.option(
    "--pretty/--compact",
    default=True,
    help="Pretty-print JSON (default: pretty).",
)
def run(source, config, output, pretty):
    """Run the transformation pipeline on one or more sources."""
    parsed: list[tuple[str, str]] = []
    for s in source:
        if ":" not in s:
            raise click.BadParameter(
                f"Each --source must be TYPE:PATH, got: {s!r}",
                param_hint="--source",
            )
        src_type, _, src_path = s.partition(":")
        parsed.append((src_type.strip().lower(), src_path.strip()))

    try:
        result = run_pipeline(parsed, config_path=config)
    except (ValueError, FileNotFoundError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    text = json.dumps(result, indent=2 if pretty else None, ensure_ascii=False)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        click.echo(f"Written to {output}", err=True)
    else:
        click.echo(text)


if __name__ == "__main__":
    cli()
