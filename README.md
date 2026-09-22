# Truco Uruguayo — Simulación Monte Carlo

Estima mediante simulación Monte Carlo probabilidades en una mano de Truco Uruguayo. Incluye experimentos de **flor** y **envido**.

---

## Reglas implementadas

- Mazo español de **40 cartas** (sin 8 ni 9).
- **6 jugadores**, 2 equipos de 3: J1, J3, J5 = Equipo A; J2, J4, J6 = Equipo B.
- La **muestra** (carta en posición 19 del mazo barajado) define el palo de las piezas.
- El **12 del palo de la muestra** actúa como la propia muestra (cuenta como pieza si el número de la muestra está en {2, 4, 5, 10, 11}).

### Flor

Un jugador **tiene flor** si su mano cumple alguna de:
- **Flor derecha**: 3 cartas del mismo palo.
- **2 o más piezas**: 2 o más cartas del palo de la muestra con número en {2, 4, 5, 10, 11}.
- **1 pieza + par**: 1 pieza y las *otras* 2 cartas son del mismo palo entre sí.

Puntaje de flor (distinto del envido):

| Combinación | Fórmula |
|---|---|
| 3 piezas | `max_pieza + (2ª_pieza % 10) + (3ª_pieza % 10)` — máx. 47 |
| 2 piezas + otra | `max_pieza + (2ª_pieza % 10) + pts_carta3` |
| 1 pieza + 2 del mismo palo | `pieza + pts_carta2 + pts_carta3` (suma las tres) |
| Flor derecha | `pts_carta1 + pts_carta2 + pts_carta3 + 20` |

### Envido

Puntaje por carta:
- **Piezas** `{2→30, 4→29, 5→28, 11→27, 10→27}` (el 12 de la muestra usa el número de la muestra).
- **Negras** (10, 11, 12 sin ser pieza): 0 puntos.
- **Resto**: valor nominal.

Puntaje de la mano:
- **Tiene pieza**: `valor_pieza + max(otras dos)` — máx. 37.
- **2 del mismo palo**: `suma de las dos + 20` — máx. 33.
- **Todos distintos**: `max` de las tres — máx. 7.

---

## Estructura del proyecto

```
truco.py                          # Lógica del juego, flor, envido, motores de simulación
report.py                         # Funciones de presentación
main.py                           # CLI — despacha al experimento indicado
experimentos/
  experimento_flor.py             # P(≥2 del mismo equipo con flor)
  experimento_envido.py           # P(oponente > X | yo tengo Y envido)
  experimento_envido_equipo.py    # Umbral óptimo para tocar envido como pie
  experimento_flor_decision.py    # Umbral óptimo para subir flor (escenario 1v2)
  experimento_flor_decision_1v1.py # Umbral óptimo para subir flor (escenario 1v1)
  experimento_envido_1v1.py        # Umbral óptimo para tocar envido (escenario 1v1)
convergencia.ipynb                # Notebook: convergencia de la estimación con n
decision_flor.ipynb               # Notebook: análisis de decisión de flor (1v2)
results/                          # Resultados guardados automáticamente
plots/                            # Gráficos generados por los notebooks
```

---

## Uso

```bash
# Experimento de flor
uv run main.py --experimento flor --n 100000
uv run main.py --experimento flor --n 1000 10000 100000 --seed 42
uv run main.py --experimento flor --n 10000 --ejemplo

# Experimento de envido (condicional individual)
uv run main.py --experimento envido --n 1000000

# Umbral óptimo para tocar envido como pie
uv run main.py --experimento envido_equipo --n 5000000

# Decisión de flor (escenario 1v2)
uv run main.py --experimento flor_decision --n 1000000

# Decisión de flor (escenario 1v1)
uv run main.py --experimento flor_decision_1v1 --n 1000000

# Umbral envido 1v1
uv run main.py --experimento envido_1v1 --n 1000000

# Notebooks
uv run jupyter notebook convergencia.ipynb
uv run jupyter notebook decision_flor.ipynb
```

Los resultados se guardan automáticamente en `results/{experimento}_n{n}_seed{seed}.txt`.

---

## Entrenamiento RL

### Agentes disponibles

| Agente | Archivo | Descripción |
|--------|---------|-------------|
| `RandomAgent` | `agents/random_agent.py` | Acción legal al azar. Baseline mínimo. |
| `ThresholdAgent` | `agents/threshold_agent.py` | Umbrales derivados de los experimentos MC. Gana ~65-70% contra random. Mejor oponente basado en reglas. |
| `RLAgent` (checkpoint) | `training/self_play.py` | Carga cualquier `.zip` y lo usa como agente. Se usa internamente en self-play. |

### Pipeline completo

```
[BC pre-training] ──→ [Fase 4: threshold] ──→ [Fase 6: MC-enhanced] ──→ [Fase 5: self-play]
    bc_init.zip         truco_threshold_final      (próximo paso)         truco_selfplay_final
    (hecho)             (hecho, 5M pasos)                                 (no iniciado)
```

La lógica de cada fase:

- **BC pre-training**: la política imita al `ThresholdAgent` con cross-entropy (~92% accuracy). Inicializa los pesos mucho más cerca de una política razonable que el inicio aleatorio.
- **Fase 4**: PPO fine-tuning contra `ThresholdAgent`. Aprende a superar la política MC.
- **Fase 6**: continúa Fase 4 con inyección directa de conocimiento MC: cabezas auxiliares supervisadas por las tablas de probabilidad, V_MC en la observación, y recompensa ajustada por sorpresa.
- **Fase 5**: self-play contra pool de checkpoints propios (+ 20% ThresholdAgent para evitar colapso). La etapa más larga y la que produce el modelo final.

### Estado actual (abril 2026)

| Fase | Checkpoint | Pasos | ep_rew_mean | explained_variance | Tiempo real |
|------|-----------|-------|-------------|-------------------|-------------|
| BC pre-training | `bc_init.zip` | — | — | — | ~5 min |
| Fase 4 | `truco_threshold_final.zip` | 5M | 0.30 | 0.466 | 23 min |
| Fase 6 | `truco_threshold_final.zip` | +5M | — | — | 42 min |
| Fase 5 | — | — | — | — | en curso |

> `bc_init.zip` y los checkpoints de Fase 4 (`truco_threshold_*.zip`) son útiles como baselines de benchmarking — no borrar.
> `truco_selfplay_final.zip` (apr 6) es de una corrida que cargó `bc_init.zip` directamente, saltándose la Fase 4. Ignorar para entrenar, conservar como referencia.

### Comandos para entrenar el modelo top

Ejecutar en orden:

```bash
# Fase 6 — MC-enhanced fine-tuning (~25 min)
uv run training/train.py --opponents threshold --steps 5000000 \
    --load checkpoints/truco_threshold_final.zip \
    --aux-heads --mc-rollouts 10 --mc-potential-reward \
    --n-envs 32

# Fase 5 — self-play (~4-6h)
uv run training/train.py --opponents selfplay --steps 50000000 \
    --load checkpoints/truco_threshold_final.zip \
    --aux-heads --mc-rollouts 10 --mc-potential-reward \
    --n-envs 32
```

> Para la Fase 5 reemplazar `--load checkpoints/truco_threshold_final.zip` con el checkpoint de salida de la Fase 6 una vez que esté disponible.

### Estimación de tiempos (32 envs, RTX 4050, i5-13500HX)

| Fase | Pasos | FPS estimado | Tiempo estimado |
|------|-------|-------------|-----------------|
| BC pre-training | — | — | ~5 min |
| Fase 4 (threshold) | 5M | ~4900 | ~17 min |
| Fase 6 (MC-enhanced) | 5M | ~3500 | ~25 min |
| Fase 5 (self-play) | 50M | ~1500–2000 | ~4–6 h |

La Fase 6 es más lenta que la Fase 4 por los rollouts MC en cada `reset()` (10 rollouts/episodio × 32 envs en paralelo). La Fase 5 es más lenta porque los agentes oponentes cargan checkpoints desde disco en cada episodio.

### Reanudar desde un checkpoint intermedio

```bash
uv run training/train.py --opponents selfplay --steps 50000000 \
    --load checkpoints/truco_selfplay_10000000.zip
# → retoma automáticamente desde el paso 10 000 000
```

> `*_final.zip` no contiene información de paso; si se pasa como `--load`, el entrenamiento arranca desde el paso 0 con los pesos cargados.

### Argumentos principales

| Argumento | Default | Descripción |
|-----------|---------|-------------|
| `--opponents` | `threshold` | Tipo de oponentes: `threshold`, `random`, `selfplay` |
| `--steps` | `5_000_000` | Total de pasos de entrenamiento |
| `--n-envs` | `8` | Entornos paralelos (SubprocVecEnv). No conviene superar el número de cores disponibles |
| `--checkpoint-freq` | `500_000` | Cada cuántos pasos guardar un checkpoint intermedio |
| `--load` | — | Checkpoint desde el cual cargar el modelo. Si el nombre sigue el patrón `*_<steps>.zip`, el script detecta automáticamente cuántos pasos ya están hechos y retoma desde ahí |
| `--shaped-reward` | `False` | Activa recompensa con shaping en vez de recompensa dispersa |
| `--aux-heads` | `False` | Cabezas auxiliares de predicción (envido/flor win-prob) supervisadas con tablas MC |
| `--lambda-aux` | `0.1` | Peso inicial de la pérdida auxiliar (se anela a 0) |
| `--aux-anneal-steps` | `10_000_000` | Pasos para llevar lambda a 0 |
| `--mc-rollouts` | `0` | Rollouts aleatorios por episodio para estimar V_MC en `obs[169]` (0 = desactivado) |
| `--mc-potential-reward` | `False` | Recompensa terminal ajustada por V_MC (amplifica resultados sorpresivos) |
| `--seed` | `42` | Semilla global |

### Métricas de entrenamiento

| Métrica | Qué indica | Tendencia saludable |
|---------|-----------|---------------------|
| `ep_rew_mean` | Win rate proxy: `(1 + valor) / 2` | ↑ hacia ~0.3–0.5 |
| `explained_variance` | Calidad de la función de valor | ↑ hacia 1.0 |
| `entropy_loss` | Aleatoriedad de la política | ↓ lentamente en magnitud |
| `approx_kl` | Cambio de política por update | < 0.05 |
| `clip_fraction` | % de updates clippeados | < 0.1 |

El log de entrenamiento se escribe en `logs/train.log`. Después de cada checkpoint aparece una línea de progreso con FPS real y ETA:
```
Progress: 5,000,000 / 50,000,000 steps  (10.0%)  fps=1842  ETA=6h 47m
```

### Jugar contra el agente

No hay script interactivo aún. `scripts/benchmark.py` enfrenta agentes entre sí de forma headless. Para jugar una partida real contra el modelo entrenado habría que construir un CLI o UI que acepte input humano y lo conecte a `TrucoGame`.

### Experimentos

Los números históricos de entrenamiento (BC warm-start, plateau de threshold,
los dos colapsos de self-play, el de-confound de rotación de asiento) están
reconstruidos con citas a la fuente en [`docs/experiments/`](docs/experiments/README.md),
enlazados a las hipótesis correspondientes en `gamekit/docs/research/`.

---

## Agregar un experimento nuevo

1. Crear `experimento_nombre.py` con un dict `EXPERIMENTO`:

```python
EXPERIMENTO = {
    "description": "descripción del experimento",
    "simulate": lambda n, seed: ...,   # retorna un dict con al menos "n" y "seed"
    "report_fn": ...,                  # función que imprime el resultado
    # "ejemplo_fn": ...,               # opcional, para --ejemplo
}
```

2. Ejecutar con `uv run main.py --experimento nombre --n 1000000`.

---

## Resultados

### Flor

| Experimento                     | Resultado                          | n          | Semilla |
| ------------------------------- | ---------------------------------- | ---------- | ------- |
| P(≥2 del mismo equipo con flor) | ~11.75% (IC 95%: [11.69%, 11.81%]) | 10 000 000 | 42      |

### Envido

| Experimento                                  | Resultado                          | n         | Semilla |
| -------------------------------------------- | ---------------------------------- | --------- | ------- |
| P(algún oponente >20 pts \| yo tengo 30 pts) | ~98.09% (IC 95%: [97.98%, 98.20%]) | 1 000 000 | 42      |
| P(algún oponente >30 pts \| yo tengo 30 pts) | ~66.0% (IC 95%: [65.60%, 66.38%])  | 1 000 000 | 42      |

### Umbral envido 1v1

Escenario: yo toco envido contra un único oponente (sin agregación de equipo).
Supuesto: empate → pierdo.

| Envido (Y) | P(ganar) | Referencia |
| ---------- | -------- | ---------- |
| ≤ 27       | < 47%    | No tocar |
| **28**     | **~54%** | **Cruza 1/2 → conveniente** |
| 29         | ~59%     | Favorable |
| 30         | ~66%     | Favorable |
| 33         | ~82%     | Muy favorable |
| 37         | 100%     | Garantizado (máximo posible) |

**Conclusión: el umbral mínimo para tocar envido 1v1 es 28 puntos.**

> Resultado completo: `results/envido_1v1_n1000000_seed42.txt`

### Umbral para tocar envido como pie

Supuesto: el pie pierde en caso de empate. La decisión se basa en el **mejor envido del equipo** (conocido vía señas).

| Mejor envido del equipo | P(ganar) | Recomendación      |
| ----------------------- | -------- | ------------------ |
| ≤ 32                    | < 41%    | No tocar           |
| 33                      | ~51%     | Límite — coin flip |
| 34                      | ~66%     | Favorable          |
| 35                      | ~83%     | Muy favorable      |
| 36                      | ~93%     | Casi seguro        |
| 37                      | 100%     | Garantizado        |

**Conclusión: el umbral mínimo para tocar envido como pie es 33 puntos de equipo**, y aun así es prácticamente un coin flip. Con 34+ la ventaja es clara.

> Resultado completo: `results/envido_equipo_n5000000_seed42.txt`

### Decisión de flor (escenario 1v2)

Escenario: yo soy el único con flor en mi equipo; los dos rivales tienen flor.
Supuesto: empate = pierdo.

| Pts de flor (X) | P(ganar) | Referencia |
| --------------- | -------- | ---------- |
| ≤ 27            | 0%       | —          |
| 28–35           | 2%–36%   | Por debajo de 1/2 |
| 36              | ~44%     | Aún por debajo de 1/2 |
| **37**          | **~60%** | **Cruza 1/2 → conviene subir** |
| **38**          | **~65%** | **Cruza 2/3 → EV pasivo > 0** |
| 39              | ~75%     | —          |
| 43+             | ≥ 99%    | Casi garantizado |

**Conclusiones:**
- **X ≥ 37**: subir la apuesta tiene EV mayor que jugar pasivo.
- **X ≥ 38**: incluso el juego pasivo es rentable en esperanza.
- **X ≤ 36**: ceder es la jugada óptima.

> Resultado completo: `results/flor_decision_n1000000_seed42.txt`

### Decisión de flor (escenario 1v1)

Escenario: yo soy el único con flor en mi equipo; exactamente 1 rival tiene flor.
Payoffs simétricos (+3/-3), por lo que hay un único umbral: **P > 1/2**.

| Pts de flor (X) | P(ganar) | Referencia |
| --------------- | -------- | ---------- |
| ≤ 33            | < 39%    | No tocar |
| 34              | ~46%     | Por debajo de 1/2 |
| **35**          | **~55%** | **Cruza 1/2 → conveniente** |
| 36              | ~65%     | Favorable |
| 37              | ~73%     | Muy favorable |
| 40+             | ≥ 90%    | Casi garantizado |

**Conclusión: el umbral mínimo para subir la flor en 1v1 es 35 puntos.**

> Resultado completo: `results/flor_decision_1v1_n1000000_seed42.txt`
