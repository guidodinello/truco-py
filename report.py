"""
Utilidades de presentación y guardado de resultados.
"""


class Tee:
    """Escribe simultáneamente a múltiples streams."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def imprimir_resultado_generico(r):
    n_filtradas = r["n_filtradas"]
    print(f"\n{'=' * 55}")
    print(f"  Simulación genérica  |  n total = {r['n']:,}  |  semilla = {r['seed']}")
    print(f"{'=' * 55}")
    print(f"  Denominador (filtro) : {n_filtradas:,}")
    print(f"  Éxitos               : {r['exitos']:,}")
    print(f"  Probabilidad est.    : {r['p'] * 100:.4f}%")
    print(f"  IC 95%               : [{r['ic_low'] * 100:.4f}% , {r['ic_high'] * 100:.4f}%]")
    print(f"  Error estándar       : {r['se'] * 100:.4f}%")
    print(f"{'=' * 55}")
