# Demo — Retail Sales Insights: de la spec al Zero-UI

La demo demuestra dos resultados distintos utilizando **especificaciones de producto independientes de la plataforma**:

1. **Spec 01:** un agente convierte requisitos de negocio en una aplicación web y un servicio de análisis de ventas.
2. **Spec 02:** el mismo servicio se hace consumible en lenguaje natural desde el asistente, sin rehacerlo.

## Material

- [Spec 01 — Producto y dashboard](../specs/retail-sales-insights-01-app.md).
- [Spec 02 — Acceso Zero-UI](../specs/retail-sales-insights-02-zero-ui.md).
- [Dataset determinista y valores esperados](../data/README.md).
- [Guía técnica del presentador](execution-guide.md).

## Qué se entrega al agente

**Únicamente la spec correspondiente y sus datos de referencia.** No es necesario entregar al agente la guía técnica de la demo. Las instrucciones de descubrimiento y consumo de la plataforma deben proceder de los contratos MCP, el catálogo, los Golden Paths, los estándares y las skills que el agente ya tenga configurados.

La guía de ejecución existe para que el presentador compruebe el resultado y pueda diagnosticar incidencias, **no para indicarle al agente cómo debe resolver cada paso**.

## Qué queremos observar

- Si el agente descubre las capacidades disponibles sin que la spec le ordene usar una herramienta concreta.
- Si aplica los estándares corporativos y controles de calidad.
- Si crea una solución de negocio correcta, con un **dashboard diseñado visualmente**, no HTML sin estilos.
- Si reutiliza el servicio existente para el canal conversacional.
- Si reconoce los errores y límites de las herramientas sin inventar datos.
