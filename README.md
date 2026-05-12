# Simulador de semáforo (intersección en cruz)

Proyecto mínimo con generador de vehículos y peatones y un algoritmo de control simple.

Características:
- Fases de semáforo alternas: `vertical` y `horizontal`.
- Duración de verde por fase: 5 ticks (supuesto).
- Vehículos: solo suben (N) o van a la derecha (E). Respetan colas.
- Peatones: cruzan bidireccionalmente en los 4 pasos de cebra.

Cómo ejecutar:

```bash
python main.py 100
```

También puede ejecutarse la visualización gráfica con `tkinter`:

```bash
python gui.py
```

Esto ejecuta la simulación 100 ticks e imprime estado por tick.

Notas:
- El simulador es intencionalmente simple: sirve como base para añadir visualización, sensores, modos manual/auto y pruebas.
