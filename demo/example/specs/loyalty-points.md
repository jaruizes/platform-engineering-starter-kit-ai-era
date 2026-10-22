# Spec: servicio de puntos de fidelidad

## Qué necesitamos

Los clientes ganan puntos con cada compra y queremos poder consultarlos. Necesitamos un servicio nuevo, `loyalty-points`, del equipo **checkout**, que lleve la cuenta de los puntos de cada cliente.

## Alcance de esta primera versión

Un único módulo funcional: **points**.

| Operación | Endpoint | Qué hace |
|---|---|---|
| Sumar puntos de una compra | `POST /customers/{customerId}/points` con `{ "orderId": "...", "amount": 59.90 }` | Suma 1 punto por cada euro entero del importe (59,90 € son 59 puntos). Devuelve el saldo nuevo |
| Consultar el saldo | `GET /customers/{customerId}/points` | Devuelve `{ "customerId": "...", "balance": 59 }` |

## Reglas de negocio

1. El importe tiene que ser mayor que 0. Si no lo es, se responde con un 400.
2. La misma compra (`orderId`) no suma puntos dos veces. Si se repite, se responde con el saldo actual sin cambiarlo.
3. Un cliente sin compras tiene saldo 0, no un 404.

## Criterios de aceptación

- Dado un cliente sin puntos, cuando registra una compra de 59,90 €, su saldo es 59.
- Dada una compra ya registrada, cuando se envía otra vez, el saldo no cambia.
- Dada una compra de 0 €, cuando se envía, la respuesta es 400 y el saldo no cambia.
- `./mvnw verify` pasa, incluidas las reglas de arquitectura.

## Fuera de alcance

Canjear puntos, caducidad y eventos. Para esta versión basta con guardar los datos en memoria, sin base de datos.

## Cómo construirlo

El servicio debe seguir arquitectura Spring y sigue los estándares de ingeniería de la empresa.
