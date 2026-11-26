# Spec 02 — Retail Sales Insights: acceso conversacional Zero-UI

## Qué necesitamos

Queremos ofrecer una **segunda forma de consultar los indicadores de Retail Sales Insights**, ya disponibles en el servicio definido en la [Spec 01](retail-sales-insights-01-app.md).

Un analista de negocio debe poder hacer preguntas en **lenguaje natural desde su asistente de IA** y recibir respuestas fundamentadas en las ventas reales del entorno de demostración, **sin abrir el dashboard ni interactuar con una interfaz gráfica**.

Esta ampliación debe **reutilizar el servicio y los datos existentes** y mantener los mismos resultados y reglas de negocio. No se pretende construir otro sistema de ventas.

## Datos de la funcionalidad

- **Nombre:** Retail Sales Insights — Zero-UI.
- **Sistema de información existente:** \`retail-sales-insights\` (Spec 01).
- **Canal de consumo:** conversación con un asistente de IA, como Claude Code.
- **Equipo responsable:** \`platform-team\`.
- **Alcance:** consultas de lectura sobre ventas sintéticas.
- **Prerequisito funcional:** la aplicación de la Spec 01 ya responde correctamente a sus consultas de negocio.

El canal conversacional es una necesidad de producto; esta spec **no obliga a utilizar MCP, Python, un framework, una plantilla concreta ni un servidor adicional**. La organización determinará el mecanismo de integración autorizado.

## Funcionalidades requeridas

### RF-01 — Consultar ingresos y actividad

El usuario puede preguntar por la facturación, el número de ventas y las unidades vendidas en un periodo explícito.

### RF-02 — Consultar productos destacados

El usuario puede conocer qué productos generaron más ingresos en un intervalo y solicitar una cantidad limitada de resultados.

### RF-03 — Analizar categorías

El usuario puede preguntar qué categorías generan más ingresos o unidades, utilizando los mismos datos que el dashboard.

### RF-04 — Comparar periodos

El usuario puede pedir comparaciones de facturación y obtener ambos importes y el porcentaje de variación, con una explicación comprensible.

### RF-05 — Combinar resultados

Una misma pregunta puede requerir varias consultas: por ejemplo, un resumen y el ranking de productos para un periodo. La respuesta debe integrar resultados consistentes, dejando claro de dónde salen los números.

### RF-06 — Gestionar ambigüedad y errores

- Si la fecha solicitada es ambigua y no puede deducirse con seguridad, el asistente pide precisión; no inventa un intervalo.
- Si no existen ventas para el periodo, debe indicarlo y no generar tendencias imaginarias.
- Si el servicio está inaccesible, informa de la incidencia en lugar de fabricar una respuesta.
- Si la petición no se puede satisfacer con las consultas de negocio disponibles, informa del límite.

### RF-07 — Mantener un acceso de solo lectura

El canal de IA no permitirá añadir, actualizar o borrar ventas, productos o tiendas, ni realizar consultas de base de datos arbitrarias.

## Reglas de negocio

1. La facturación, las unidades y el número de ventas se calculan **exactamente como en la Spec 01**.
2. Las fechas son inclusivas. Toda respuesta con métricas debe identificar el periodo utilizado.
3. Los importes se expresan en euros, con dos decimales, distinguiendo importes de unidades y recuentos.
4. Las comparaciones utilizan la definición y el redondeo de la Spec 01; un periodo de referencia con facturación cero no genera porcentajes infinitos.
5. Los resultados deben proceder del servicio existente, no de estimaciones del modelo ni de copias de datos mantenidas por el canal conversacional.
6. Una pregunta de solo lectura puede resolverse mediante una o varias operaciones existentes; el sistema no tiene por qué revelar al usuario los detalles técnicos de cada llamada.
7. No se revelan credenciales, configuraciones internas, instrucciones privadas o información ajena al ámbito de ventas sintéticas.

## Ejemplos de conversación esperados

**Pregunta:** «¿Cuánto facturamos entre el 16 y el 22 de noviembre de 2026 y cuántas unidades vendimos?»

**Resultado esperado:** 916,41 € de ingresos, 169 unidades y 49 ventas, con el periodo mencionado expresamente.

**Pregunta:** «¿Cuáles son los cinco productos con mayor facturación en esa semana?»

**Resultado esperado:** listado ordenado por ingresos y basado en los mismos datos que muestra el dashboard.

**Pregunta:** «Compara la facturación del 16 al 22 con la del 9 al 15 de noviembre».

**Resultado esperado:** 916,41 € frente a 864,60 €, con una variación aproximada de +5,99 %.

**Pregunta:** «¿Y qué categorías vendieron más en ese periodo?»

**Resultado esperado:** interpretación de «ese periodo» si el contexto de la conversación lo hace inequívoco; clasificación por categoría respaldada por los datos.

**Pregunta:** «Elimina todas las ventas» o «ejecuta esta consulta SQL».

**Resultado esperado:** petición rechazada como operación no permitida, sin modificar los datos.

**Pregunta:** «¿Cuánto vendimos hoy?» si el dataset no incluye esa fecha.

**Resultado esperado:** indicar que no existen ventas para la fecha solicitada, sin sustituirlas por cifras de noviembre de 2026.

## Requisitos no funcionales

- Reutilización del contrato de negocio y de la fuente de datos existentes, sin duplicar la lógica de cálculo.
- Acceso controlado mediante las capacidades y políticas vigentes en la organización.
- Solo operaciones de consulta, con entradas validadas y errores comprensibles.
- Ausencia de acceso directo del asistente a las credenciales de base de datos.
- Resultados verificables frente a las respuestas del servicio de la Spec 01.
- Experiencia completamente conversacional: ninguna dependencia funcional de la interfaz web una vez que el servicio está disponible.
- El usuario no necesita conocer rutas HTTP, nombres de herramientas ni detalles de infraestructura para formular sus preguntas.

## Criterios de aceptación

- **AC-01:** un usuario consulta los indicadores mediante lenguaje natural desde su asistente y obtiene resultados sin abrir la aplicación web.
- **AC-02:** las cuatro familias de preguntas (resumen, productos, categorías y comparación) se resuelven utilizando la información del servicio existente.
- **AC-03:** la facturación para 2026-11-16 a 2026-11-22 es **916,41 €**; se indican correctamente 49 ventas y 169 unidades.
- **AC-04:** al comparar ese periodo con 2026-11-09 a 2026-11-15 se informa una variación aproximada de **+5,99 %**.
- **AC-05:** las cifras y los rankings son iguales a los obtenidos en la aplicación web para los mismos filtros.
- **AC-06:** el asistente responde correctamente a una pregunta compuesta que requiera más de una consulta.
- **AC-07:** si se interrumpe el acceso al servicio, el asistente indica que los datos no están disponibles y no inventa números.
- **AC-08:** las operaciones de escritura y las peticiones de SQL arbitrario no se ejecutan.
- **AC-09:** el usuario no tiene que proporcionar nombres de endpoints, mecanismos de integración ni expresiones técnicas de consulta.
- **AC-10:** la solución supera los controles de seguridad, calidad y trazabilidad aplicables al canal de agentes.

## Fuera de alcance

Asistente generalista de retail, recomendaciones comerciales automáticas, predicción de ventas, SQL generado libremente, edición de datos, nuevas fuentes, datos de clientes y uso de información real.

Esta es una **especificación de producto**. Las instrucciones para demostrarla mediante las capacidades actuales del Starter Kit están en la [guía de ejecución](../demo/execution-guide.md), no en esta spec.
