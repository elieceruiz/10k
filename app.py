import streamlit as st
import openai
import base64
from PIL import Image
import io
import time
from pymongo import MongoClient
import pytz
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")

# --- SECRETS ---
openai.api_key = st.secrets["openai_api_key"]
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# --- ZONA HORARIA ---
tz = pytz.timezone("America/Bogota")

# --- INTERFAZ ---
st.title("👁️ Visión GPT-4o – Proyecto 10K")
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

# Estado de sesión
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []
if "imagen_base64" not in st.session_state:
    st.session_state.imagen_base64 = None

# Función para codificar la imagen
def image_to_base64(image_file):
    return base64.b64encode(image_file.read()).decode("utf-8")

# Detectar objetos
if uploaded_file and st.button("🔍 Detectar objetos"):
    st.image(uploaded_file, caption="Imagen cargada", use_column_width=True)
    st.session_state.imagen_base64 = image_to_base64(uploaded_file)
    
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente que solo responde con una lista simple de nombres de objetos visibles en una imagen. Nada más."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{st.session_state.imagen_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": "Enumera los objetos que ves, sin descripción ni contexto. Solo nombres separados por coma."
                        }
                    ],
                }
            ],
            max_tokens=150
        )
        texto = respuesta.choices[0].message.content
        st.session_state.objetos_detectados = [x.strip() for x in texto.split(",") if x.strip()]
    except Exception as e:
        st.error(f"Error en la detección: {e}")

# Mostrar checkboxes
if st.session_state.objetos_detectados:
    st.subheader("📦 Objetos detectados:")
    elementos_ordenados = []
    for idx, obj in enumerate(st.session_state.objetos_detectados, start=1):
        if st.checkbox(f"{obj}", key=obj):
            elementos_ordenados.append(obj)

    if st.button("✅ Iniciar sesión de orden"):
        start_time = time.time()
        st.success("⏱ Cronómetro iniciado...")
        placeholder = st.empty()
        while True:
            elapsed = int(time.time() - start_time)
            minutos, segundos = divmod(elapsed, 60)
            placeholder.markdown(f"🧭 Tiempo transcurrido: **{minutos:02}:{segundos:02}**")
            time.sleep(1)
            st.rerun()

        # Guardar en Mongo al final (esta parte debes ajustar si hay un botón para detener)
        doc = {
            "timestamp": datetime.now(tz),
            "objetos": elementos_ordenados,
            "duracion_segundos": elapsed
        }
        col.insert_one(doc)

# Enlace a uso de OpenAI
st.markdown("---")
st.markdown("🔗 [Ver uso de créditos](https://platform.openai.com/usage)")