"""
CLI — Simulación Monte Carlo Truco Uruguayo

Uso:
    uv run main.py --experimento flor --n 100000
    uv run main.py --experimento flor --n 10 100 1000 10000 100000 --seed 42
    uv run main.py --experimento flor --n 10000 --ejemplo
    uv run main.py --experimento envido --n 1000000
"""

import argparse
import importlib
import sys
from pathlib import Path

from report import Tee


def guardar_resultado(nombre, r, report_fn):
    path = Path("results") / f"{nombre}_n{r['n']}_seed{r['seed']}.txt"
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        original = sys.stdout
        sys.stdout = Tee(original, f)
        report_fn(r)
        sys.stdout = original
    print(f"  → guardado en {path}")


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo — Truco Uruguayo")
    parser.add_argument(
        "--experimento",
        required=True,
        help="Nombre del experimento (ej: flor, envido)",
    )
    parser.add_argument(
        "--n",
        type=int,
        nargs="+",
        default=[1_000_000],
        help="Tamaño(s) de muestra. Ej: --n 100 1000 100000",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semilla para el generador aleatorio (default: 42)",
    )
    parser.add_argument(
        "--ejemplo", action="store_true", help="Mostrar una mano de ejemplo detallada"
    )
    args = parser.parse_args()

    mod = importlib.import_module(f"experimentos.experimento_{args.experimento}")
    exp = mod.EXPERIMENTO

    print(f"\n{exp['description']}")

    for n in args.n:
        r = exp["simulate"](n, args.seed)
        guardar_resultado(args.experimento, r, exp["report_fn"])

    if args.ejemplo:
        ejemplo_fn = exp.get("ejemplo_fn")
        if ejemplo_fn:
            ejemplo_fn(args.seed)
        else:
            print("  (este experimento no tiene --ejemplo)")


if __name__ == "__main__":
    main()
