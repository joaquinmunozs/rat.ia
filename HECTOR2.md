# Hector2 — el filtro de confianza sobre el reenvío del aliado

*23-ago-2026.*

## El problema que resuelve

`reenviar_ofertas.py` reenvía lo que el canal del aliado publica, confiando
en que su clasificación ("esto es un error/oferta de precio") es correcta.
No lo es siempre: el caso real que lo destapó fue un jugo en caja que el
aliado anunciaba bajando de $2.000 a $400, cuando ese producto siempre costó
$400. Es el mismo fraude de anclaje de precio que Consumer Reports midió en
más de 30% de las "ofertas" de grandes retailers en EE.UU. en 2024, y que la
FTC trata como engañoso salvo que el "antes" sea un precio real y
documentado.

## La idea central

No se inventa una segunda vara para medir descuentos: se reusa la que
`baseprecios.evaluar` de Héctor ya tiene, afinada con semanas de datos reales
(referencia = mínimo real de 30 días, 7 días mínimos de historial, piso de
35%-40% según categoría). Si el producto del aliado ya está en la base de
Héctor, Hector2 le pregunta a esa lógica si la caída declarada es real —no
recalcula nada propio.

## Las piezas

| Archivo | Qué hace |
|---|---|
| `hector2_filtro.py` | Extrae URL/precio/% del mensaje, detecta si el link es de una tienda que Héctor ya vigila, filtra ruido de categoría (libros, tarjetas de regalo, accesorios), cruza contra la base de Héctor o verifica en vivo, y devuelve un veredicto: `confirmado` / `sin_verificar` / `descartado`. |
| `hector2_db.py` | Base propia (`hector2.db`, separada de `precios.db`): cada mensaje que pasó por el filtro, confianza acumulada por canal de origen, y el umbral adaptativo por tópico. |
| `descargar_base_hector.py` | Baja el respaldo diario de `precios.db` que `hector.yml` ya sube como GitHub Release (`respaldo-base`), de solo lectura, y lo refresca cada 4h. |
| `reenviar_ofertas.py` | Enganche: llama al filtro antes de reenviar, decide el tópico final según el ritmo, y registra todo. |

## Los tres veredictos, y qué significa cada uno

- **confirmado** — el producto está en la base de Héctor y la caída se
  sostiene contra su historial real, o se verificó en vivo que el precio
  actual coincide con lo declarado. Se manda tal cual.
- **sin_verificar** — no hay con qué cruzar (tienda fuera del catálogo de
  Héctor, o la verificación en vivo no se pudo hacer por un error de red).
  No es evidencia de que esté mal, tampoco de que esté bien. Se manda
  marcado ("🔎 sin verificar del todo") y con más exigencia que un confirmado.
- **descartado** — evidencia directa de que está mal: no calificó contra la
  base real, el precio en vivo no coincidió, o es ruido de categoría. No se
  manda, pero SIEMPRE queda registrado en `hector2.db` — nada se pierde sin
  dejar rastro auditable.

## El ritmo adaptativo: ni mudo, ni saturado

Cada tópico tiene un objetivo de mensajes/día (`OBJETIVOS_RITMO` en
`reenviar_ofertas.py`) y un umbral de puntaje que se ajusta solo, una vez por
hora, mirando cuánto se mandó en las últimas 24h — mismo patrón AIMD que
`vigilante.py` ya usa para el ritmo de peticiones, con pasos simétricos a
propósito (la asimetría fue lo que dejó a `falabella.com` atrapada en su piso
el 20-ago). Si un tópico manda de menos, el umbral baja; si satura, sube.
Nada queda mudo del todo: lo que no llega al umbral cae a
`VIGIA_TOPICO_DUDOSOS` en vez de descartarse, siempre que ese tópico esté
configurado.

Los números de `OBJETIVOS_RITMO` son un punto de partida (1-2 posts/día es la
referencia para canales no-noticiosos, 4+ ya deteriora el alcance), **no una
medición**. Calibrarlos con los datos reales de `hector2.db` después de la
primera semana es el siguiente paso natural.

## La parte evolutiva: confianza por canal

`hector2_db.confianza_canal` acumula, por canal del aliado, qué fracción de
sus mensajes terminó confirmada vs. descartada (con un piso de 5 casos antes
de confiar en el número, igual que `baseprecios` no le cree a una mediana con
pocas lecturas). Un canal que demuestra acertar sube su puntaje base cuando
no hay con qué verificarlo del todo; uno ruidoso lo baja. Con semanas de
datos, esto se puede convertir en un reporte propio — como el semanal de
costos de Higgsfield — que diga qué canales del aliado valen la pena de
verdad.

## Qué falta (fases siguientes, no bloqueantes)

- Calibrar `OBJETIVOS_RITMO` con datos reales de `hector2.db`.
- Un reporte periódico de confianza por canal (hoy el dato se acumula pero
  nadie lo lee todavía).
- Extender `RUIDO_IRRELEVANTE` con lo que aparezca en los primeros
  "descartados" reales que no debieron descartarse, o viceversa.

## Cómo probarlo

```bash
python -m unittest test_hector2 -v      # sin red
python descargar_base_hector.py         # baja la base real (~600 MB hoy)
```
