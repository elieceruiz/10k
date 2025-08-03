import streamlit as st
import openai
from pymongo import MongoClient
from PIL import Image
from datetime import datetime, timedelta
import pytz
import base64
import io
import time

# === CONFIGURACIÓN INICIAL ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")

# === SECRETS ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# === VARIABLES DE SESIÓN ===
if "objeto_en_proceso" not in st.session_state:
    st.session_state.objeto_en_proceso = None

if "tiempo_inicio" not in st.session_state:
    st.session_state.tiempo_inicio = None

if "cronometro_general" not in st.session_state:
    st.session_state.cronometro_general = timedelta()

if "historial" not in st.session_state:
    st.session_state.historial = []

if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []

# === INTERFAZ PRINCIPAL ===
st.title("👁️ Visión GPT-4o – Proyecto 10K")
st.markdown("📤 **Sube una imagen**")

uploaded_file = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

# === DETECCIÓN ===
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagen cargada", use_container_width=True)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    img_bytes = buffer.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode()

    if not st.session_state.objetos_detectados:
        with st.spinner("🔍 Detectando objetos con IA..."):
            try:
                prompt = f"""Describe brevemente los objetos presentes en esta imagen. Solo enuméralos como una lista, sin explicar, sin contexto ni oraciones. Sé breve y conciso. Imagen en base64:\n{img_base64[:1000]}..."""
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150
                )
                texto = respuesta.choices[0].message.content.strip()
                objetos = [obj.strip("•- ").strip() for obj in texto.split("\n") if obj.strip()]
                st.session_state.objetos_detectados = objetos
            except Exception as e:
                st.error(f"Error en la detección: {e}")

# === LISTADO DE OBJETOS CON ORDEN ===
if st.session_state.objetos_detectados:
    st.subheader("📦 Objetos detectados:")
    nuevo_orden = []
    for i, objeto in enumerate(st.session_state.objetos_detectados):
        col1, col2 = st.columns([4, 1])
        with col1:
            seleccionado = st.checkbox(f"{objeto}", key=f"obj_{i}")
        with col2:
            if seleccionado:
                orden = st.number_input(f"{i+1}", min_value=1, max_value=10, step=1, key=f"orden_{i}")
                nuevo_orden.append((orden, objeto))

    # === INICIAR ORDENAMIENTO ===
    if nuevo_orden:
        nuevo_orden.sort()
        objeto_actual = nuevo_orden[0][1]
        if st.button("🚀 Iniciar ordenamiento"):
            st.session_state.objeto_en_proceso = objeto_actual
            st.session_state.tiempo_inicio = datetime.now(tz)
            st.rerun()

# === CRONÓMETRO INDIVIDUAL Y REGISTRO ===
if st.session_state.objeto_en_proceso and st.session_state.tiempo_inicio:
    st.subheader(f"⏱ Ordenando: {st.session_state.objeto_en_proceso}")
    tiempo_actual = datetime.now(tz)
    tiempo_transcurrido = tiempo_actual - st.session_state.tiempo_inicio
    segundos = int(tiempo_transcurrido.total_seconds())
    minutos = segundos // 60
    st.info(f"🧭 Tiempo transcurrido: {minutos:02d}:{segundos%60:02d}")

    lugar = st.text_input("📍 ¿Dónde va este objeto?", key="lugar_objeto")
    if st.button("✅ Finalizar objeto"):
        doc = {
            "objeto": st.session_state.objeto_en_proceso,
            "duracion_segundos": segundos,
            "minutos": minutos,
            "lugar": lugar,
            "timestamp": datetime.now(tz)
        }
        col.insert_one(doc)
        st.session_state.cronometro_general += tiempo_transcurrido
        st.session_state.historial.append(doc)
        st.session_state.objetos_detectados.remove(st.session_state.objeto_en_proceso)
        st.session_state.objeto_en_proceso = None
        st.session_state.tiempo_inicio = None
        st.rerun()

# === CRONÓMETRO GLOBAL ===
total_sec = int(st.session_state.cronometro_general.total_seconds())
total_min = total_sec // 60
total_hr = total_min // 60
st.success(f"📈 Tiempo total acumulado: {total_hr}h {total_min%60}m {total_sec%60}s")
st.markdown("[🔗 Ver uso en OpenAI](https://platform.openai.com/usage)")