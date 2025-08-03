import streamlit as st
from datetime import datetime, timedelta
import pytz
from pymongo import MongoClient
import openai
from PIL import Image
import io
import base64
import re

# === CONFIG STREAMLIT ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CONEXIÓN A MONGODB ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# --- CLAVE OPENAI ---
openai.api_key = st.secrets["openai_api_key"]

# --- ZONA HORARIA CO ---
tz = pytz.timezone("America/Bogota")

# === FUNCIÓN IA PARA DETECCIÓN ===
def analizar_imagen_con_openai(image_bytes):
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    respuesta = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": "Detecta objetos presentes en esta imagen. Responde con una lista Python con los nombres de los objetos detectados."},
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}],
            },
        ],
        temperature=0,
        max_tokens=150,
    )
    return respuesta.choices[0].message.content.strip()

# === SUBIDA DE IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)
    image_bytes = imagen.read()

    try:
        texto = analizar_imagen_con_openai(image_bytes)
        st.subheader("📄 Respuesta del modelo:")
        st.code(texto)

        match = re.search(r"\[.*?\]", texto, re.DOTALL)
        if match:
            try:
                objetos = eval(match.group(0))
                if isinstance(objetos, list):
                    st.session_state.objetos_detectados = objetos
                else:
                    st.warning("⚠️ La respuesta no es una lista.")
            except Exception as e:
                st.error(f"❌ Error al interpretar los objetos: {e}")
                st.code(match.group(0))
        else:
            st.warning("⚠️ No se detectó una lista clara en la respuesta.")
    except Exception as e:
        st.error(f"Error en la detección: {e}")

# === LISTA DE OBJETOS DETECTADOS ===
if "objetos_detectados" in st.session_state:
    st.subheader("📦 Objetos detectados:")
    if "objetos_orden" not in st.session_state:
        st.session_state.objetos_orden = {}

    for i, obj in enumerate(st.session_state.objetos_detectados):
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.checkbox(f"{obj}", key=f"chk_{i}"):
                st.session_state.objetos_orden[obj] = None
        with col2:
            if obj in st.session_state.objetos_orden:
                st.session_state.objetos_orden[obj] = st.number_input(
                    f"Orden", min_value=1, step=1, key=f"orden_{i}"
                )

    if st.button("▶️ Iniciar cronómetro"):
        st.session_state.tiempo_inicio = datetime.now(tz)
        st.success("⏱ Cronómetro iniciado...")

# === CRONÓMETRO Y REGISTRO ===
if "tiempo_inicio" in st.session_state:
    tiempo_actual = datetime.now(tz)
    tiempo_transcurrido = tiempo_actual - st.session_state.tiempo_inicio
    segundos = int(tiempo_transcurrido.total_seconds())
    minutos = segundos // 60
    st.info(f"🧭 Tiempo transcurrido: {minutos:02d}:{segundos%60:02d}")

    if st.button("✅ Finalizar y guardar"):
        for obj, orden in st.session_state.objetos_orden.items():
            if orden is not None:
                doc = {
                    "objeto": obj,
                    "orden": orden,
                    "duracion_segundos": segundos,
                    "timestamp": datetime.now(tz),
                }
                col.insert_one(doc)
        st.success("✅ Registro guardado en MongoDB.")
        del st.session_state.tiempo_inicio
        del st.session_state.objetos_orden

# === PROGRESO GLOBAL HACIA LAS 10.000 HORAS ===
registros = list(col.find({}))
total_segundos = sum(r.get("duracion_segundos", 0) for r in registros)
total_horas = total_segundos / 3600
st.markdown(f"⏳ **Horas acumuladas hacia las 10.000:** `{total_horas:.2f}`")

# === ENLACE A USO OPENAI ===
st.markdown("---")
st.markdown("🔗 [Ver saldo y uso de OpenAI](https://platform.openai.com/usage)")