# Bitácora — martes 25 de agosto de 2026 (tarde)

> Se construyó el motor de selección de Instagram para Rat.IA: qué ofertas
> y qué errores de precio suben, cuándo, y con qué texto — más la landing
> donde el DM pide correo antes de entregar el link.

Complementa [BITACORA-2026-08-25.md](./BITACORA-2026-08-25.md) (la
madrugada: el aviso propio de Hector2 y el fix del link de producto).

---

## Las reglas, tal como las dio Joaquín

**Ofertas** — máximo 2 al día. Tiene que ser producto novedoso/viral/
tecnológico/hogar **Y** al menos 50% de descuento (las dos condiciones, no
basta una). Se suben 1-2 horas después de aparecer en el Telegram. Corte a
las 23:30 — nada se publica después.

**Errores de precio** — se suben 30 minutos después de aparecer en el
Telegram, a **cualquier hora** (el corte de las 23:30 no les aplica). El DM
pide correo antes de entregar el link; en ofertas el DM manda el link
directo, sin ese paso.

## De dónde salen los candidatos — sin construir nada nuevo para leerlos

De las dos fuentes que YA alimentan el Telegram de Rat.IA:

- `alertas` en precios.db — los hallazgos propios de Héctor.
- `anuncios` en hector2.db — los reenvíos verificados del aliado.

Las dos ya tenían nombre, tienda, precio, referencia, caída y el momento
exacto del aviso, gracias al trabajo de archivado de esta misma madrugada.
Ese momento es el "primera_vez_vista" del que se cuentan las 1-2h o los
30 min — **el trabajo de anoche resultó ser exactamente lo que esta pieza
necesitaba, sin retocar nada.**

## Qué cuenta como "novedoso/viral/tecnológico/hogar"

Se reusaron los patrones que ya existen y están calibrados con casos reales,
en vez de inventar una lista nueva:

- `categorias.RE_ELECTRONICOS` / `RE_HOGAR` — lo tecnológico y lo hogar.
- `caliente.IMANES` — la lista de "esto genera cola" (Apple, gaming, marcas
  de reventa, drones, LEGO…), que es la definición real de "novedoso/viral".

**Un caso real lo destapó al escribir las pruebas:** el propio ejemplo que
dio Joaquín — "Starlink Mini" — no calzaba en ninguna de las dos listas. Se
agregó a `IMANES`. Efecto secundario bueno: eso también sube la frecuencia
de vigilancia de Héctor para ese tipo de producto, no sólo la selección de
Instagram — es la misma lista, con dos usos.

## Error de precio: la vara ya existía

`baseprecios.UMBRAL_ERROR_GRAVE` (0.85) es el mismo corte que se definió
esta madrugada para separar "Ofertas 70%" de "Errores de precio" en el
propio Telegram. Se reusa tal cual — un número, un solo lugar.

## El orquestador: `ratia_ig_selector.py`

Una pasada hace, en orden: lee el Telegram reciente de las dos fuentes,
registra candidatos nuevos (idempotente — si ya estaba, no lo toca),
vence los que se pasaron de su ventana, califica los pendientes, decide
cuáles se publican EN ESTE INSTANTE (respetando cupo diario, corte de
horario y el ranking por puntaje), y arma la pieza de cada uno.

**Mismo principio de seguridad que ya tenía `ratia_publicar`:** sin
`--confirmar`, arma todo y loguea, nunca llama a Blotato. Un selector
automático que publica solo, sin que nadie lo haya visto correr en
producción al menos una vez, es el tipo de incidente que ya se evitó una
vez con esa misma regla.

**Probado de punta a punta contra las bases reales** (de solo lectura,
nunca escribe en `precios.db`): un candidato inyectado a mano llegó hasta
`generar_pieza()` y se frenó limpio por falta de `ANTHROPIC_API_KEY` /
`KIE_API_KEY` — exactamente donde tenía que frenarse hoy, no antes ni
después.

### Un detalle de infraestructura que hubo que resolver en el camino

El respaldo de `precios.db` que se descarga (la copia de solo lectura,
generada por la última corrida real de `hector.yml`) todavía no tiene las
columnas `nombre`/`tienda` que se agregaron a `alertas` esta madrugada —
son de la migración de código de hoy, y el respaldo es de ANTES. Se hizo
tolerante: sin esas columnas, las filas vienen con `nombre`/`tienda` en
`None` y simplemente no califican para Instagram hasta que el respaldo se
regenere solo con la próxima corrida real. No rompe, no inventa datos.

## Los textos, sin precio ni link

**Ofertas:** sólo comercio + nombre + "comenta OFERTA y te lo mando por
DM". Sin precio (ya está en la imagen) y sin link — un link en la
descripción penaliza el alcance en Instagram, y tampoco captura nada.

**Errores:** mismo principio, más el aviso explícito de que el DM va a
pedir correo antes del link — decirlo de entrada evita que alguien comente,
no reciba nada al toque, y piense que el bot está roto.

## La landing del DM: `condorai.cl/ratia/oferta`

Adonde apunta el link que ManyChat manda por DM. Lee los datos del
producto de la URL (`?producto=&tienda=&url=&tipo=`), pide correo, y recién
al enviar guarda el lead y muestra el botón al link real.

**El gate de consentimiento es de BASE, no sólo de interfaz.** La policy de
`insert` en `ratia_leads` exige `consintio=true and consintio_en is not
null` — probado en vivo contra el proyecto real: sin consentir, la base
rechaza el insert; consintiendo, pasa; y nadie externo puede leer los leads
de otro (sin policy de `select` para `anon`/`authenticated`).

**El link no se oculta por seguridad** — viaja igual en la URL de esta
misma página. Es una barrera de intención, no de acceso: el mismo
principio que "deja tu correo para el PDF".

### El bug que no era bug: Chrome headless por debajo de ~450px

Una primera captura de la landing en un viewport de 390px mostraba la
tarjeta desbordando el borde derecho. Se aisló con una reproducción mínima,
sin ninguna clase propia — y **seguía desbordando**, incluso con un `<div>`
vacío. Confirmado subiendo el ancho de a poco: a 500px renderiza perfecto.
**Chrome headless con `--window-size` por debajo de ~450px no respeta el
ancho pedido** en este build — no es un bug de la página. Lección para la
próxima captura de QA visual: no confiar en anchos angostos con esta
herramienta, usar 500px+ para simular móvil.

---

## Estado al cerrar

- `rat.ia`: commit `d72811a`, pusheado. 22 pruebas nuevas, suite completa
  (97+ pruebas entre todos los archivos) en verde.
- `condor-ai`: commit `c4f96cc`, pusheado y **desplegado en vivo** —
  verificado bajando el bundle real de `condorai.cl/ratia/oferta`.
- `ratia_leads` aplicada y verificada con inserts reales contra el
  Supabase de Cóndor (fila de prueba borrada después).

## Lo que falta, sin construir todavía

- **El carrusel real.** Hoy `publicar_oferta` sube una sola imagen; falta
  armar las 2 slides (la segunda es `slide2_predeterminada()` de
  `plantillas_ratia.py`, que sigue sin commitear).
- **La foto real del producto.** `_foto_de()` en el selector devuelve
  vacío — falta bajar la ficha y leer `og:image`, mismo patrón que ya usa
  `hector2_filtro.imagen_de` para los reenvíos del aliado.
- **Credenciales:** `BLOTATO_API_KEY`, `KIE_API_KEY`, `ANTHROPIC_API_KEY`,
  `RATIA_IG_CUENTA_ID`.
- **ManyChat** — cuenta y API key, pendiente de Joaquín. El flujo
  "comenta → DM con este link" se configura dentro de ManyChat mismo (su
  constructor visual), no es código.
- **Enganchar el selector a algo que corra solo** — hoy es un script que
  se ejecuta a mano; falta un cron o sumarlo al loop de
  `reenviar_ofertas.py`.
