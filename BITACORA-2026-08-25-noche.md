# Bitácora — martes 25 de agosto de 2026 (tarde-noche)

> Cubre los **10 commits** que van de las 14:42 en adelante, o sea todo lo que
> pasó después de que cerrara
> [BITACORA-2026-08-25-tarde.md](./BITACORA-2026-08-25-tarde.md) (que llega
> hasta `0753174`, 13:20).
>
> Tres bloques: **convenios** y **libros** (sesión de la tarde), y una tanda de
> la noche que arranca con dos capturas de Joaquín mostrando avisos malos en el
> grupo.
>
> Complementa [BITACORA-2026-08-25.md](./BITACORA-2026-08-25.md) (madrugada) y
> la de la tarde. Contexto del proyecto: [CONTEXTO.md](./CONTEXTO.md) y
> [20-agosto-bitacora-hector.md](./20-agosto-bitacora-hector.md).

---

## Resumen en una frase

Se cerró el trabajo de convenios y el de libros; después Joaquín reportó dos
avisos rotos y resultó que el arreglo ya existía pero **no estaba desplegado**,
y que debajo había un segundo agujero que ningún deploy resuelve — más una
asimetría vieja: cosas que Hector2 filtraba y Héctor no.

---

## ⚠️ LO PRIMERO QUE HAY QUE SABER

**Todo lo que toca Hector2 está en `master` y NO está corriendo.**

El auto-deploy por push nunca se enganchó en Railway (deuda documentada en la
bitácora del 20-ago §5: el repo se conectó por API, no por el flujo de
"Connect GitHub"). Un `git push` no despliega nada. Hoy eso costó una tanda de
avisos falsos: el arreglo del §3 estaba commiteado **dos minutos después** del
aviso malo que iba a evitar, y siguió sin correr.

| Qué | Dónde corre | ¿Está en vivo? |
|---|---|---|
| Héctor (`baseprecios`, `vigia`, `vigilante`) | GitHub Actions, desde `master` | ✅ sí, solo |
| Hector2 (`reenviar_ofertas`, `hector2_filtro`) | Railway `ratia-reenvio` | ❌ **hasta el redeploy** |
| Selector de Instagram | Railway, dentro del mismo proceso | ❌ y además apagado a propósito (§7) |

Verificado: la corrida `32918956607` (01:26 UTC del 26-ago) corre sobre
`ec068ec`, así que **el corte de gift cards del §5 ya está en producción**. Lo
del §3, §4, §6 y §7 no.

**Lo que hay que pedirle a Joaquín**, en este orden:

1. Redeploy de `ratia-reenvio` apuntando a `0c1975c`.
2. Autorizar el **GitHub App de Railway** sobre el repo desde el dashboard —
   es la solución de fondo; sin eso, cada arreglo futuro corre el mismo riesgo
   de quedarse en `master`.

---

## §1 · Convenios banco-comercio: la tercera fuente de contenido

`b1bd2a2` + `b4f2038`

Pedido de Joaquín el 25-ago: alianzas banco-comercio ("40% en Copec con Lider
Bci") y promociones de cadenas, además de las caídas de precio de Héctor.

**Ningún banco chileno ofrece webhook para esto.** Se investigó en vivo y se
encontró `panguiapp.com`: agregador real y activo, páginas pre-renderizadas
(HTML real, sin JS), sin protección anti-bot, y su `robots.txt` permite
explícitamente `/bancos/` y `/tiendas/`. Cubre BancoEstado, Banco de Chile,
BCI, Santander, CMR Falabella, Cencosud Scotiabank, Mach, Tenpo; del lado
comercios, McDonald's, KFC, Wendy's, Turbus, Flixbus y las tres grandes
cadenas de farmacias.

Marca cada oferta como "Verificado hoy" o "Sin verificar hace N días" — esa es
la señal real que habilita el "publica sola si pasa la verificación".

### Las piezas

| Archivo | Qué hace |
|---|---|
| `convenios_pangui.py` | El extractor. Probado contra HTML real bajado en vivo (`fixtures/pangui_*.html`), no inventado |
| `convenios_ciclo.py` | Cuándo toca republicar cada convenio |
| `convenios_fuentes.py` | Qué páginas se vigilan y a qué tópico va cada una |
| `convenios_monitor.py` | El orquestador: baja las 16 páginas, extrae, decide y ejecuta |
| `convenios_pieza.py` | La pieza de Instagram para convenios |
| `convenios_textos.py` | Los textos |

### Tres decisiones que no son obvias

**El delimitador de cada oferta es "Ver detalle", no "% de descuento".** Esa
segunda frase se repite dentro de la descripción de una misma oferta y partía
una oferta en varias. Se encontró escribiendo las pruebas, no leyendo el
código.

**El comercio/emisor NO se adivina por capitalización** — aparece en mayúscula
total, mixta, de todo menos consistente. Se recibe como parámetro de quien ya
sabe qué página está vigilando.

**La pieza de convenios no reusa la de retail.** Esa gira en torno a un
"antes → ahora" y a la foto real del producto, y un convenio no tiene ninguna
de las dos. Es puramente tipográfica.

> **REGLA CRÍTICA.** Se le pide EXPLÍCITAMENTE al modelo que no dibuje ningún
> logo. Un modelo de imagen siempre devuelve algo: si le pides el logo de un
> banco, dibuja algo *parecido*, y publicar una versión deformada de la marca
> registrada de un banco real —afirmando además un descuento suyo— es un
> problema más caro que un precio mal escrito. La verificación además le
> pregunta al modelo si ve logos dibujados y descarta la pieza si dice que sí.

### Los topes los encontró el primer ensayo real

La primera pasada contra las 16 páginas devolvió **1.347 convenios** con
acción pendiente. Sin tope, la primera corrida con `--confirmar` habría
mandado 1.347 mensajes de golpe y silenciado el grupo en minutos. No es un
caso de borde: es el arranque **normal** de un monitor que ve todo el catálogo
por primera vez.

`aplicar_topes`: 25 avisos de Telegram por pasada y 2 de Instagram al día,
priorizados por descuento. Lo que no entra **no se marca en la base**, así que
la pasada siguiente lo reevalúa — no se pierde. Verificado: 1347 → 25 en la
corrida real.

Los 9 tópicos de Telegram quedaron creados y las variables
`CONVENIOS_TOPICO_*` seteadas en Railway.

---

## §2 · Libros: fuera por completo, con tres cortes

`3fea28a` + `048e1ca`

Pedido de Joaquín: *"quites todos los libros de hector 2 y hector en el grupo
telegram y nunca mas avisaremos ofertas ni errores de precios con ellos"*.

No es una preferencia nueva: es el final de un problema documentado desde el
7-ago. En su momento se parchó en `caliente.IMANES` (un libro nunca entra a la
lista caliente), pero la barrida normal los seguía leyendo y avisando.

**Tres cortes, porque uno solo no alcanzaba:**

1. `tiendas.py` — fuera `buscalibre.cl` y `antartica.cl` (de 44 a 42 tiendas).
   Evita volver a **leerlas**, pero no borra lo ya guardado.
2. `baseprecios.evaluar` — **corte duro por dominio, y este es el que
   importa**: el vigilante avisa recorriendo la BASE, no la lista de tiendas, y
   quedan **56.549 fichas de Antártica** cargadas (contadas, no estimadas). Va
   en `evaluar` porque es el único punto por el que pasan las dos rutas —la
   barrida y la lista caliente—; en cualquier otro lado quedaba una puerta
   abierta.
3. `hector2_filtro.es_irrelevante` — ahora también por dominio. Al sacar los
   dominios del catálogo, el chequeo `rubro == "libros"` dejó de dispararse
   (llegan como tienda desconocida), así que un reenvío con link a Antártica y
   un título que no diga "libro" habría pasado.

### El bug que introdujo el commit anterior

`hector.yml` **repite los dominios a mano en su matriz de shards** — es una
segunda fuente de verdad. Al sacar las dos librerías de `tiendas.py`, esos
dominios quedaron en la matriz (shards 0 y 3). Y `tiendas.py` no ignora un
dominio desconocido: aborta con `SystemExit`.

**Efecto real: los shards 0 y 3 habrían reventado ENTEROS en la próxima
corrida** — la mitad de la cobertura de Héctor caída. Se encontró antes de que
corriera, comprobándolo y no deduciéndolo:

```
HECTOR_TIENDAS="...,antartica.cl" python -c "import tiendas"
-> HECTOR_TIENDAS nombra tiendas que no existen: antartica.cl
```

Los 4 shards vuelven a cargar (6+11+12+13 = 42, cuadra con `tiendas.py`). Hay
3 pruebas nuevas para que la matriz y `tiendas.py` no se desincronicen otra
vez.

`limpiar_libros.py` saca las fichas de la base con `olvidar_url` (que además
las anota en `descartadas`, si no el descubrimiento del lunes las vuelve a
meter). **Hay que correrlo en Actions, no en el PC de nadie** — la base real
vive allá; para eso está el input `limpiar_libros` del workflow. De todos
modos `particionar_base.py` borra lo que no sea del shard, así que las fichas
de librerías se van solas en la próxima corrida.

---

## §3 · El aviso que se contradecía solo

`f85c5ef`

Dos bugs reportados por Joaquín en el tópico de errores de precio.

### El aviso se contradecía a sí mismo

Caso real, salió publicado:

```
$139.930 -> $11.990 (91.4%)
...
Precio histórico: $11.990   25/08
sondeo propio de los últimos 30 días
```

El mismo mensaje anunciaba −91% **y** mostraba nuestro propio sondeo diciendo
que el producto cuesta $11.990. Joaquín: *"toallas que estaban en 120.000
(imposible) y hoy bajaron a 11000 (ese siempre es precio normal)"*.

Causa: `_armar_aviso` buscaba referencia entre los precios propios **mayores**
al actual. Si no había ninguno —o sea, si nuestro sondeo decía que el precio de
hoy es el normal— caía a `referencia_declarada`, el "antes" del aliado, y
publicaba ese número inflado.

**La lógica estaba al revés:** tener datos propios que NO muestran caída es
EVIDENCIA EN CONTRA de la oferta, no falta de información. Ahora eso corta el
aviso. Y se eliminó el fallback a `referencia_declarada` por completo: ese
número es justo el que puede estar inflado, y publicarlo como propio convertía
a Rat.IA en el mismo canal del que se quiere diferenciar.

> Se pierde alcance; se conserva que un "−91%" de Rat.IA signifique algo.

### El link PRODUCTO llevaba a "Unauthorized"

El redirector del aliado devuelve 403 **también en un navegador real**, no solo
a un script. Se lo había dejado como último recurso suponiendo que a una
persona sí le serviría. No le sirve.

Hallazgo: **la URL real del producto viaja en BASE64 dentro del link de la
imagen** (`img2.ofertasshark.cl/.../f:jpg/<base64>`). Verificado:

```
aHR0cHM6Ly9jYW5ub25ob21l... -> https://cannonhome.cl/toalla-de-bano-...
```

`url_real_desde_imagen` la rescata y `detectar_producto` la prefiere sobre el
redirector. Si aun así lo único que hay es el redirector, no se publica: un
link que no abre deja el aviso inútil.

---

## §4 · El reloj Curren: una observación suelta no es una referencia

`9bf5e6b`

Joaquín mandó dos capturas: el tópico "Ofertas 70%" con

```
Curren Reloj Kree1904 Quartz Hombre Talla Única
$46.990 -> $14.091 (70.0%)
Precio histórico: $14.091   25/08
sondeo propio de los últimos 30 días
```

y el link PRODUCTO abriendo una página roja que dice **Unauthorized**.

### Eran dos problemas, no uno

**El primero ya estaba arreglado.** El mensaje es de las 17:45; `f85c5ef` (§3)
es de las **17:47**. Reproducido contra `master`: el código actual no publica
ese aviso ni ese link. Lo que salió al grupo era código viejo — ver la
advertencia del principio.

**El segundo no lo arregla ningún deploy.** Cambiando sólo el sondeo propio,
el mismo reloj seguía publicando:

| Sondeo propio | Resultado |
|---|---|
| 1 observación, 2 días de historia | publicaba **−70,0%** contra $46.990 |
| 1 observación de hace **200 días** | publicaba |
| 1 observación de hace **1 minuto** | publicaba |

Tres cosas mal:

1. **`historico_propio` no filtraba por fecha.** El mensaje afirma
   textualmente *"sondeo propio de los últimos 30 días"* y la consulta SQL no
   tenía ninguna condición de tiempo. La frase podía estar respaldada por una
   observación de hace un año.
2. **Una sola observación bastaba** para fijar una referencia. `baseprecios`
   exige 5 lecturas y 7 días para lo mismo; este camino paralelo no exigía
   nada.
3. **Por ahí volvía a entrar el ancla del aliado.** `precios_vistos` guarda su
   `precio_declarado`, y el aliado publica el mismo hallazgo en 2-3 canales a
   la vez (bitácora del 20-ago). Bastaba que uno trajera un precio más alto
   para que al minuto siguiente fuera "nuestra" referencia — justo después de
   que `f85c5ef` sacara ese número por la puerta de adelante.

### La vara

**Decisión de Alejandro**, sobre la alternativa más blanda de 2 observaciones
en días distintos: **la misma vara de Héctor**, 5 observaciones y 7 días,
dentro de la ventana de 30.

> Cuesta alcance en las tiendas fuera del catálogo —son las que menos sondeo
> propio acumulan— y a cambio un porcentaje publicado por Rat.IA siempre tiene
> respaldo detrás.

**Efecto esperable los próximos días:** el volumen del aliado va a bajar
bastante, y **no hay que leerlo como una falla nueva**. `hector2.db` se
borraba entera en cada deploy hasta el arreglo de la madrugada, así que el
sondeo propio arranca casi de cero y necesita ~7 días de acumulación. Sólo
afecta a tiendas **fuera** del catálogo de Héctor: las que Héctor ya vigila
sacan su referencia de `baseprecios` y siguen igual.

`respaldo_propio` es función nueva porque `historico_propio` agrupa POR PRECIO
y corta en `limite`: sirve para MOSTRAR el sondeo, no para MEDIR cuánto
respaldo hay. Dos cosas distintas que se estaban usando como una.

### 6 pruebas que nunca se ejecutaron

`test_jsonld_producto_correcto.py` (del arreglo del extractor del 24-ago) está
escrito estilo pytest, y **pytest no está instalado ni figura en
`requirements.txt`**. `python -m unittest` respondía `Ran 0 tests` — que se lee
igual que un éxito. Es el mismo modo de falla del `if __name__` que había
quedado a mitad de `test_hector2_aviso.py`.

Verificadas a mano antes de engancharlas: **las seis pasan**. Faltaba el
enganche, no el arreglo del extractor.

---

## §5 · Gift cards: lo que Hector2 filtraba y Héctor no

`ae94d1c`

Salió de verificar un pendiente de `CONTEXTO.md` §9: *"hushpuppies.cl y vans.cl
descubren 3.190 fichas y miden CERO"*.

**Ese pendiente ya estaba resuelto.** El manejo de `ProductGroup`/`hasVariant`
de Shopify lo cubrió y nadie lo había verificado. Medido contra el sitio real:

```
vans.cl        -> precio=29990  "Zapatilla Authentic Negro Vans - 34.5"
hushpuppies.cl -> precio=29990  "Gift Card Cinturón Belt Bar Hush Puppies"
```

Y ese segundo nombre destapó lo demás.

### Una gift card no tiene precio: su precio ES su monto

Un cambio del monto por defecto de la ficha se lee como una caída, y el
suscriptor no puede aprovechar nada — comprar $10.000 en gift card cuesta
$10.000. Lo mismo con entradas, suscripciones, cursos y pólizas.

`hector2_filtro` ya lo filtraba para los reenvíos del aliado; `baseprecios` no
filtraba nada. **Exactamente la misma asimetría que tenían los libros hasta el
§2**: arreglado en un lado, abierto en el otro. El corte va en `evaluar` por la
misma razón que el de librerías.

### El regex heredado se comía ropa, muebles y ferretería

Antes de mudarlo se probó contra nombres reales, y descartaba en silencio:

```
"Polera Manga Larga Hombre Nike"      -> por "Manga"    ← y 5 más tomados
"Camisa Manga Corta Lino Mujer"          del sitemap real de tricot.cl
"Mesa de Entrada Recibidor Madera"    -> por "Entrada"
"Puerta de Entrada Roble 90x200"      -> por "Entrada"
"Seguro de Puerta Infantil Pack 6"    -> por "Seguro"
"Cerradura con Seguro Interior"       -> por "Seguro"
"Casco Seguro Bicicleta Adulto"       -> por "Seguro"
```

Es la **lección #5 del 20-ago** otra vez ("un regex de sanidad puede descartar
en silencio lo más importante"), la misma que ya costó el canal "80".

- `manga` fuera: en retail chileno "manga larga/corta" es muchísimo más
  frecuente que el cómic, y los cómics ya caen por `comic|libro|revista` y por
  el corte de librerías por dominio.
- `entrada` sólo si el nombre nombra un evento. "Mesa de entrada" pasa.
- `seguro` exige tipo de póliza (vida/salud/automotriz/…). El lookahead viejo
  sólo salvaba "seguro de vidrio", y **en ferretería "seguro" es una PIEZA** —
  construmart.cl mide el 100% de sus 9.886 fichas.
- `curso` exige "de/online/virtual/presencial".

> Que estos aparezcan recién ahora no es casualidad: en `hector2_filtro` el
> patrón corría sobre anuncios del aliado, donde esas palabras casi no salen.
> Aplicado a las 360.000 fichas de Héctor tiene otro costo. **Un filtro no se
> muda de contexto sin volver a probarlo.**

**Ojo:** ese descarte de ropa **está pasando ahora mismo en Hector2**, en
silencio, con motivo de categoría. Se arregla con el redeploy.

El patrón vive en `baseprecios` (Héctor lo necesita en `evaluar` y
`hector2_filtro` ya importa `baseprecios`; al revés habría import circular).
Dos copias se habrían ido separando, que es como empezó esta asimetría.

El corte sólo aplica **cuando hay nombre**: sin nombre no se puede afirmar que
sea ruido, y descartar por las dudas perdería fichas buenas.

### Las variantes que faltaban (`34c006a`)

El patrón heredado cubría "gift card", "giftcard" y "tarjeta **de** regalo".
Probado contra cómo nombra esto el retail chileno de verdad, se colaban cuatro
formas: `Tarjeta Regalo Jumbo` (sin el "de"), `Vale Regalo Sodimac`,
`eGift Card Cencosud` y `e-Gift`.

**Lo que NO se agregó:** `tarjeta prepago`. Una SIM prepago es un producto
real y vendible; cortarla sería repetir el error de arriba — ampliar un filtro
sin mirar qué más cae dentro.

Los tres patrones nuevos exigen la palabra que los delata pegada al lado, así
que los productos **de regalo que sí se venden** siguen pasando. Verificado,
no supuesto: `Papel de Regalo`, `Bolsa de Regalo`, `Caja de Regalo`, `Set de
Regalo`, `Moño de Regalo`, `Tarjeta Prepago Entel SIM`, `Tarjeta Madre ASUS`.

---

## §5 bis · Lo que se revisó y NO era un problema

Está acá para que nadie lo reinvestigue. Todo medido, no supuesto.

| Sospecha | Resultado |
|---|---|
| **tricot.cl leería siempre el mismo nodo del JSON-LD** — dos URLs del sitemap devolvían "Jeans hombre clásico" a $9.990, que es la firma exacta del bug de bata.cl del 24-ago | **Falsa alarma.** Son dos SKU distintos del mismo modelo (`-31516` y `-31539`); un tercer producto da precio y nombre distintos. El extractor está sano |
| **falabella.com no descubriría nada** — su sitemap devolvió 0 URLs | **Artefacto de la prueba.** El árbol se recorre en anchura y un `tope` chico corta antes de llegar al nivel de las fichas. Con `tope=200` y `tope=3000` devuelve URLs normales |
| **Héctor podría tener el defecto del reloj** (§4): un aviso cuyo histórico contradiga su propio porcentaje | **No puede.** En las dos rutas —`vigia.py:507` y `vigilante.py:1105`— `evaluar` se llama **antes** de `guardar`, así que el precio de hoy no entra en su propia referencia. El contrato del docstring se cumple en ambas |
| **hushpuppies.cl y vans.cl medirían 0%** (`CONTEXTO.md` §9) | **Ya estaba resuelto**, ver §5 |
| **`categorias.RUIDO` sería otra asimetría** como la de los libros y las gift cards | **No lo es.** No descarta el hallazgo: sólo impide clasificarlo en Electrónicos/Hogar, así que el aviso igual sale por Ofertas. Es otra clase de filtro |

Quedó a medias un **barrido de salud de extractores** contra las 13 tiendas
restantes del catálogo: se detuvo a propósito porque quedó colgado (muy
probablemente en tottus, que bloquea por IP) y dejaba peticiones corriendo sin
supervisión — la IP que se quema es la de casa (lección #6 del 20-ago). Las
que sí alcanzó a medir están sanas: falabella, hites, spdigital, tricot, vans
y hushpuppies. **Reintentarlo desde el runner de Actions, no desde un PC.**

---

## §6 · La foto real del producto

`ec068ec`

Cierra el pendiente de la bitácora de la tarde: *"`_foto_de()` en el selector
devuelve vacío"*. Sin esto **ninguna oferta podía llegar a publicarse**:
`ratia_pieza_ia.generar_pieza` se niega a armar la pieza sin foto, así que el
selector entero terminaba en nada.

**No se lee `og:image` a mano, a propósito.** `extractor.extraer` ya lo
encuentra Y valida el resultado, y esa validación no es de adorno:
spdigital.cl publica de verdad

```html
<meta property="og:image" content="https:undefined">
```

que tiene forma de URL y host inexistente. Leído a mano se guarda como si
fuera una foto y el carrusel falla recién al publicar, cuando Instagram no
puede bajarla — o sea el error aparece en el único momento en que ya no se
puede corregir.

**Ante la duda, sin foto.** Cualquier problema devuelve `""` y no una foto
aproximada. Una pieza de Instagram con la foto de OTRO producto es la versión
visual del mismo fraude que Hector2 existe para filtrar.

Verificado contra fichas reales:

```
vans.cl         -> https://www.vans.cl/cdn/shop/files/VN000EE3_BKA_1.jpg
tricot.cl       -> https://www.tricot.cl/dw/image/v2/BGHZ_PRD/...
URL inexistente -> (sin foto, se frena solo)
```

---

## §7 · El selector de Instagram corre solo, y por defecto no publica

`0c1975c`

Cierra *"engancharlo a algo que corra solo"* de la bitácora de la tarde. Hasta
hoy era un script a mano, así que en la práctica no publicaba nunca.

Va **dentro de `reenviar_ofertas.py`** como una tercera tarea periódica, no en
un cron aparte: ese proceso ya está levantado 24/7, ya mantiene fresca la copia
de `precios.db` (`_tarea_refresco_base`) y ya tiene abierta la `hector2.db` de
donde salen los candidatos. Un cron tendría que rehacer las tres cosas.

### `RATIA_IG_AUTO` — y por defecto no hace nada

| Valor | Qué pasa |
|---|---|
| *(sin definir)* | **La tarea ni siquiera arranca.** Idéntico a antes |
| `ensayo` | Corre las pasadas y loguea qué publicaría. **NO publica** |
| `1` | Publica de verdad |

El escalón del medio es el que importa: deja mirar en los logs de Railway qué
habría salido, los días que haga falta, antes de que nada llegue a Instagram.
Es la regla que ya traía `ratia_publicar` — *"un selector automático que
publica solo, sin que nadie lo haya visto correr en producción al menos una
vez, es el tipo de incidente que ya se evitó una vez con esa misma regla"*.

Un valor raro (`si`, `true`, `yes`) arranca en **ensayo**: la única cadena que
publica es `1`.

### Conexiones propias, no las del bot

`_pasada_instagram` abre las suyas y las cierra en un `finally`. No reusa
`_ESTADO["con_hector"]`/`["con_h2"]` a propósito: esas están serializadas con
`_DB_LOCK`, y una pasada baja fichas, llama a un modelo de imágenes y publica.
Tener el lock tomado todo ese rato dejaría el reenvío del aliado **congelado
durante minutos** — el mismo error que el 11-ago mantenía el lock de escritura
tomado durante descargas HTTP. `hector2.db` está en WAL, así que una segunda
conexión convive sin problema.

### Dos fallas silenciosas que las pruebas cubren

- **Si una pasada revienta, la tarea no puede morir.** El reenvío a Telegram
  seguiría andando, el servicio se vería sano, y nadie notaría que dejó de
  publicarse en Instagram.
- **Las conexiones se cierran aunque la pasada reviente.** Una filtrada cada 10
  minutos deja el servicio sin descriptores en unos días.

El intervalo (10 min) **no es el retraso de publicación**: las ventanas reales
—30 min para errores, 1-2 h para ofertas, corte 23:30— las sigue decidiendo
`ratia_seleccion`. Esta tarea sólo pregunta seguido.

---

## Un pendiente que estaba mal dimensionado

El **tópico Supermercado (350)** figura desde el 20-ago como "creado, faltan
patrones y la variable". Es más grande que eso: aunque se agreguen los
patrones, `PRECIO_MINIMO` ($20.000) y `AHORRO_MINIMO` ($8.000) lo dejarían
mudo igual.

| Producto | Precio | Para ahorrar $8.000 debe caer |
|---|---:|---:|
| Aceite Chef 1L | $3.490 | **229%** |
| Café Nescafé Gold 170g | $9.990 | 80% |
| Detergente Ariel 3L | $12.990 | 62% |
| Leche Colún 1L x12 | $13.990 | 57% |
| Pañales Huggies XG 60un | $24.990 | 32% |

Necesita **umbrales propios**, igual que los tuvo Vuelos (`UMBRAL_VUELOS` y el
salto de `PRECIO_MINIMO`). Eso es decisión de negocio y quedó **sin tocar** a
propósito.

---

## Qué queda abierto

### Bloquea que esto sirva de algo

1. **Redeploy de Railway a `0c1975c`.** Los §3, §4, §6 y §7 están en `master` y
   no corren. Es lo primero.
2. **Autorizar el GitHub App de Railway** para que el auto-deploy quede
   enganchado y esto deje de repetirse.

### Para encender Instagram, en orden

3. Cargar `BLOTATO_API_KEY`, `KIE_API_KEY`, `ANTHROPIC_API_KEY`,
   `RATIA_IG_CUENTA_ID` en Railway.
4. `RATIA_IG_AUTO=ensayo` y mirar los logs unos días. **Sin el paso 3 el ensayo
   se frena en `generar_pieza` por falta de credenciales** — es lo correcto,
   pero no hay que leerlo como una falla.
5. Recién ahí `RATIA_IG_AUTO=1`.

### Sigue igual que ayer

6. **`plantillas_ratia.py` sigue sin commitear.** El carrusel de 2 slides
   depende de su `slide2_predeterminada()`; hoy sube una sola imagen.
7. **ManyChat** — cuenta y API key, pendiente de Joaquín. El flujo
   "comenta → DM" se configura en su constructor visual, no es código.
8. Extractor propio para **Dr. Simi, RutPay y Mercado Pago** (convenios).
9. **Tópico Supermercado**: decidir sus umbrales (ver arriba).
10. **Plan Workers de US$5/mes** de Cloudflare. Héctor es el 99,8% de la cuota
    gratis y tumba el webhook de ventas de Planeta Shop.
11. **Calibrar `OBJETIVOS_RITMO`** con los datos reales de `hector2.db`.

---

## Nota de método

Dos cosas de hoy valen como regla general:

> **Un arreglo commiteado no es un arreglo desplegado.** Antes de dar por
> resuelto un reporte de Joaquín, verificar qué commit está corriendo de
> verdad. Hoy el arreglo del §3 existía dos minutos después del aviso que
> tenía que evitar, y siguió saliendo mal por horas.

> **Un filtro no se muda de contexto sin volver a probarlo.** El regex del §5
> era correcto sobre anuncios del aliado y descartaba ropa y ferretería sobre
> el catálogo completo. Lo mismo vale para umbrales y para cualquier heurística
> calibrada contra una fuente y reusada en otra.

---

## Commits

```
b1bd2a2  Convenios banco-comercio: extractor, ciclo de republicacion y textos
b4f2038  Convenios: monitor completo, pieza de Instagram y topes por pasada
3fea28a  Libros: nunca mas se avisan ofertas ni errores de precio de librerias
048e1ca  Libros: saca las librerias de la matriz del workflow (arregla shards 0 y 3)
f85c5ef  Hector2: no publicar caidas sin respaldo propio, ni links que no abren
9bf5e6b  Hector2: una observacion suelta no es una referencia (el reloj Curren)
ae94d1c  Hector: gift cards y entradas tampoco se avisan, y el regex deja de comerse ropa
ec068ec  Rat.IA: la pieza de Instagram usa la foto real del producto
0c1975c  Rat.IA: el selector de Instagram corre solo, y por defecto no publica nada
34c006a  Gift cards: las variantes que usa el retail chileno de verdad
```

(Más `9a4d89b`, esta misma bitácora.)

**Suite completa: 209 pruebas en verde** (por archivo y con `discover`), más los
11 `probar_*.py` que no salen a la red. `probar_tls.py` no se corrió: sale a
internet contra tiendas reales.
