# 🧹 10k – Orden Personal con IA

Este es un proyecto personal para registrar sesiones de orden físico y limpieza, como parte de un proceso disciplinado hacia las 10.000 horas de dominio.

La app permite:

- Capturar una foto desde el celular o navegador
- Detectar objetos automáticamente con IA (Roboflow)
- Seleccionar hasta 3 objetos por sesión
- Asignar un destino fijo a cada uno
- Guardar todo en MongoDB Atlas

---

## 🚀 ¿Cómo funciona?

1. Se abre desde el celular (vía Streamlit Cloud)
2. Tomás una foto del espacio desordenado
3. La IA detecta los objetos en la imagen
4. Seleccionás hasta 3 para trabajar
5. Elegís su destino: ganchos, cajón tech, reciclaje, etc.
6. Se guarda el registro de la sesión (con foto, objetos y acciones)

---

## 🧠 Tecnologías utilizadas

- [Streamlit](https://streamlit.io/) – interfaz web simple y responsiva
- [Roboflow](https://roboflow.com/) – modelo de detección de objetos
- [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) – base de datos en la nube
- Python, PIL, inference_sdk

---

## ⚙️ Requisitos

Archivo `requirements.txt`:
