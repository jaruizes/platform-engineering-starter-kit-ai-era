# Spec 01 — Retail Sales Insights: aplicación de análisis de ventas

## Qué necesitamos

Una cadena ficticia de tiendas quiere consultar de forma sencilla el comportamiento de sus ventas. Necesita una **aplicación web** con un dashboard que muestre indicadores de negocio y permita analizar distintos periodos, productos y categorías.

La solución se denominará **Retail Sales Insights**. Esta primera entrega incluye un servicio de consulta de ventas y una interfaz web. La [Spec 02](retail-sales-insights-02-zero-ui.md) añadirá otra forma de acceder a la misma información.

La solución utilizará exclusivamente datos sintéticos, sin información personal ni conexiones con sistemas de venta reales.

## Datos del producto

- **Aplicación:** Retail Sales Insights.
- **Servicio de negocio:** \`retail-sales-insights\`.
- **Aplicación web:** \`retail-sales-web\`.
- **Equipo responsable:** \`platform-team\` (propietario organizativo del ejemplo).
- **Ámbito:** consulta de datos de una cadena ficticia de tres tiendas.
- **Disponibilidad requerida:** acceso a la aplicación desde el entorno de demostración, sin publicación pública en Internet.
- **Cumplimiento:** estándares de arquitectura, desarrollo, seguridad y calidad aplicables en la organización.

Estos datos identifican el producto y sus restricciones, pero no prescriben herramientas, Golden Paths, pipelines ni procedimientos de aprovisionamiento.

## Información de negocio

El producto trabajará con tres conceptos:

- **Producto:** identificador, SKU, nombre y categoría comercial.
- **Tienda:** identificador, nombre y ciudad.
- **Venta:** identificador, producto, tienda, fecha de venta, cantidad de unidades y precio unitario.

Para que el resultado sea verificable, se facilita el [dataset de referencia](../data/README.md), con doce productos, tres tiendas y 196 líneas de venta. Los datos abarcan del **26 de octubre al 22 de noviembre de 2026**, ambos inclusive.

Los ficheros SQL y CSV proporcionados son datos de entrada de la demostración, **no instrucciones sobre cómo se debe implementar la persistencia o la carga**. El resultado debe ser consistente con esos registros y no debe sustituirlos por valores aleatorios.

## Funcionalidades requeridas

### RF-01 — Resumen de ventas

El usuario puede elegir un intervalo de fechas y consultar:

- Facturación total en euros.
- Número de ventas (líneas registradas).
- Número de unidades vendidas.

### RF-02 — Ranking de productos

El usuario puede consultar los productos con mayor facturación en el periodo elegido. El ranking presenta nombre, categoría, unidades e ingresos. Por defecto muestra los cinco primeros y admite hasta diez.

### RF-03 — Análisis por categoría

El usuario puede consultar la facturación y las unidades vendidas agrupadas por categoría, para el mismo intervalo de fechas.

### RF-04 — Comparación entre periodos

El usuario puede comparar los ingresos de dos periodos e identificar la variación porcentual. En el dashboard, el periodo de comparación por defecto es el intervalo inmediatamente anterior, con la misma duración que el seleccionado.

### RF-05 — Actualización de filtros

El usuario puede modificar las fechas y actualizar todos los indicadores de forma coherente, sin recargar manualmente toda la página.

### RF-06 — Estados de la aplicación

Cuando aún no hay datos cargados, no hay resultados para un filtro o el servicio no está disponible, la interfaz informa claramente de cada situación; nunca muestra cifras anteriores como si fueran las actuales.

## Reglas de negocio

1. **Facturación:** suma de \`cantidad × precio unitario\` de las líneas de venta del periodo, sin impuestos ni descuentos adicionales.
2. **Precisión monetaria:** los cálculos no pueden sufrir errores de coma flotante. En la interfaz, el importe se muestra como euros con dos decimales.
3. **Fechas:** los intervalos incluyen las fechas inicial y final. Las fechas son de calendario, no marcas temporales dependientes de zonas horarias.
4. **Validación:** no se admiten fechas inexistentes, intervalos invertidos o parámetros de consulta no válidos; el usuario recibe un error comprensible.
5. **Ranking:** productos ordenados por facturación descendente y, en caso de empate, por identificador ascendente.
6. **Categorías:** ordenadas por facturación descendente y, en caso de empate, alfabéticamente.
7. **Periodos sin ventas:** la facturación y los contadores son cero; los rankings no muestran productos ficticios.
8. **Variación porcentual:** \`(ingresos actuales − ingresos anteriores) / ingresos anteriores × 100\`, redondeado a dos decimales. Si el periodo anterior tiene ingresos cero, la variación es *no calculable*, nunca infinito.
9. **Consistencia:** dashboard y servicio deben mostrar los mismos importes y recuentos para los mismos filtros.

## Contrato de consulta

La solución ofrecerá un servicio de consulta que pueda utilizarse independientemente de la pantalla. Su contrato funcional mínimo es:

| Operación | Parámetros | Información devuelta |
|---|---|---|
| \`GET /api/insights/summary\` | \`from\`, \`to\` | \`{from,to,revenueCents,salesCount,unitsSold}\` |
| \`GET /api/insights/top-products\` | \`from\`, \`to\`, \`limit\` opcional (5 por defecto, máximo 10) | \`{from,to,items:[{productId,productName,category,revenueCents,unitsSold}]}\` |
| \`GET /api/insights/by-category\` | \`from\`, \`to\` | \`{from,to,items:[{category,revenueCents,unitsSold}]}\` |
| \`GET /api/insights/compare\` | \`from\`, \`to\`, \`previousFrom\`, \`previousTo\` | \`{currentRevenueCents,previousRevenueCents,changePercent}\` |

Las fechas del contrato se expresan como \`YYYY-MM-DD\` y los importes monetarios como **céntimos enteros**. La variación es un porcentaje numérico con hasta dos decimales o \`null\` cuando no pueda calcularse. Una solicitud inválida obtiene una respuesta de error de cliente, sin divulgar detalles internos.

Este contrato es un requisito de interoperabilidad: no impone arquitectura interna, librerías ni mecanismos de despliegue.

## Experiencia y diseño visual del dashboard

**Se espera una interfaz visualmente cuidada, moderna y coherente con un producto de analítica empresarial.** Una página con tipografía HTML por defecto, tablas sin formato y cifras alineadas como texto plano **no satisface esta especificación**, aunque las consultas devuelvan HTTP 200.

### Composición y jerarquía

- **Encabezado reconocible:** nombre “Retail Sales Insights”, breve descripción de la vista y zona de selección del periodo.
- **Área de filtros:** fechas inicial y final con etiquetas claras y acción “Aplicar”, integradas en una banda o panel visualmente diferenciado.
- **Indicadores principales:** tres tarjetas independientes para *Facturación*, *Ventas* y *Unidades vendidas*. Cifra principal de gran tamaño, unidad y etiqueta secundaria.
- **Comparación:** una tarjeta o sección de tendencia con importe del periodo anterior, variación porcentual y distinción visual entre crecimiento, descenso y dato no calculable.
- **Detalle:** dos paneles diferenciados para *Productos más vendidos* y *Ventas por categoría*, con tablas legibles y encabezados descriptivos.
- **Espacios y alineación:** contenido centrado con ancho máximo razonable; márgenes, separación entre secciones y alineación de importes consistentes.

### Lenguaje visual esperado

- Estética de **dashboard SaaS profesional**: limpia, contenida y con jerarquía clara, no una pantalla de administración sin estilos.
- Fondo neutro suave; superficies o tarjetas con contraste respecto al fondo; bordes o sombras discretos.
- Tipografía sans-serif legible, títulos diferenciados, números destacados y etiquetas secundarias menos prominentes.
- Paleta consistente con uno o dos colores de acento y significado claro para tendencias positivas/negativas. No depender únicamente del color para transmitir significado.
- Filas de tabla con separación adecuada; importes alineados a la derecha y datos comparables fáciles de leer.
- Estados de carga, error y ausencia de resultados presentados como componentes diseñados, no como mensajes técnicos.
- Evitar adornos excesivos, animaciones innecesarias y bibliotecas visuales pesadas para una pantalla tan sencilla.

### Responsividad, accesibilidad y calidad visual

- **Escritorio:** a 1440 × 900, se debe apreciar una composición equilibrada, sin enormes espacios vacíos ni tablas arrinconadas; los KPI se disponen en una fila o grid.
- **Móvil:** a 390 × 844, los filtros siguen siendo utilizables, las tarjetas se reorganizan y las tablas mantienen legibilidad mediante diseño adaptado o desplazamiento horizontal controlado.
- Controles con etiquetas, navegación mediante teclado, estados de foco visibles, contraste suficiente y semántica adecuada para tablas.
- Importes con formato europeo, por ejemplo \`916,41 €\`; fechas comprensibles para el usuario.
- La interfaz debe sentirse acabada tanto con datos como en carga, vacío y error.

Estos son **resultados visuales y de usabilidad exigibles**, no una prescripción de framework CSS, biblioteca de componentes, color hexadecimal o estructura de archivos. El equipo implementador elegirá cómo cumplirlos.

## Requisitos no funcionales

- Aplicación y servicio desplegables y accesibles en un entorno temporal de pruebas.
- Datos persistidos durante la vida del entorno y sin exposición de credenciales al navegador.
- Consultas de solo lectura, con validación de entradas y sin operaciones de modificación de ventas.
- Estándares corporativos de arquitectura, seguridad, pruebas y calidad aplicables.
- Evidencia automatizada de las reglas de negocio y de los estados principales del frontend.
- Tiempos de respuesta adecuados para el pequeño dataset sin requerir paginación compleja.
- Sin uso de datos personales, analítica externa ni dependencias de servicios de terceros.

## Criterios de aceptación

- **AC-01:** aplicación web y servicio de negocio disponibles y funcionando, cada uno identificable y con propietario responsable.
- **AC-02:** dataset completo accesible para las consultas: 12 productos, 3 tiendas y 196 ventas, sin registros duplicados.
- **AC-03:** para 2026-11-16 a 2026-11-22, resumen de **916,41 €**, **49 ventas** y **169 unidades**.
- **AC-04:** para 2026-11-09 a 2026-11-15, facturación **864,60 €**; la variación respecto al periodo posterior es aproximadamente **+5,99 %**.
- **AC-05:** ranking y agrupación por categoría coinciden con los cálculos del dataset; límites y ordenaciones respetan las reglas de negocio.
- **AC-06:** el servicio rechaza intervalos inválidos y no divulga errores internos; no se puede manipular libremente su consulta de datos.
- **AC-07:** cambiar el intervalo actualiza todos los componentes que dependen de él; se muestran correctamente estados de carga, vacío y error.
- **AC-08:** dashboard **visualmente diseñado**, con tarjetas KPI, filtros agrupados, paneles de análisis, tipografía jerarquizada, espaciado, colores coherentes y tablas legibles. **No se acepta HTML sin estilizar.**
- **AC-09:** vista comprobada en **1440 × 900 y 390 × 844**, sin solapamientos, desbordamientos no controlados ni pérdida de información importante.
- **AC-10:** el usuario puede acceder por teclado a filtros y acciones; los datos numéricos, etiquetas y estados son comprensibles sin depender exclusivamente del color.
- **AC-11:** comprobaciones de calidad y pruebas automatizadas aplicables superadas.
- **AC-12:** la solución puede ser consultada desde una aplicación cliente y desde otras interfaces mediante el contrato descrito.

## Fuera de alcance

Compras o pedidos nuevos, devoluciones, administración de inventario, edición de ventas, datos reales, cuentas de clientes, pagos, ingestión continua, herramientas BI externas, consultas SQL libres y el acceso conversacional de la Spec 02.

**La especificación no prescribe el proceso de construcción.** Para la ejecución guiada de la demo, existe una [guía separada](../demo/execution-guide.md).
