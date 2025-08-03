import streamlit as st
from pymongo import MongoClient
import openai
import pytz
from datetime import datetime
from PIL import Image
import io
import base64
import time

# --- CONFIGURACIÓN STREAMLIT ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CONEXIONES Y VARIABLES ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# --- ESTADO DE SESIÓN ---
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []
if "seleccionados" not in st.session_state:
    st.session_state.seleccionados = []
if "cronometro_activo" not in st.session_state:
    st.session_state.cronometro_activo = False
if "inicio_tiempo" not in st.session_state:
    st.session_state.inicio_tiempo = None

# --- SUBIDA DE IMAGEN ---
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
    image_bytes = uploaded_file.read()
    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

    if st.button("🔎 Detectar objetos"):
        with st.spinner("Detectando objetos..."):
            try:
                prompt = f"""
Describe solo los objetos físicos visibles en esta imagen, en formato lista separada por comas, sin introducción ni conclusiones. Imagen codificada: {img_base64}
                """

                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Eres un asistente visual que solo nombra objetos físicos visibles."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0
                )

                texto = response.choices[0].message.content

                if ":" in texto:
                    texto = texto.split(":", 1)[-1]

                objetos = [
                    item.strip(" .").capitalize()
                    for item in texto.split(",")
                    if 2 < len(item.strip()) < 40 and not any(p in item.lower() for p in ["ayudarte", "imagen", "analizar", "lo siento", "no puedo"])
                ]

                st.session_state.objetos_detectados = objetos
                st.session_state.seleccionados = []
                st.rerun()

            except Exception as e:
                st.error(f"Error en la detección: {e}")

# --- VISUALIZAR OBJETOS DETECTADOS ---
if st.session_state.objetos_detectados:
    st.subheader("📦 Objetos detectados:")
    seleccionados = []

    for obj in st.session_state.objetos_detectados:
        if st.checkbox(obj, key=obj):
            seleccionados.append(obj)

    st.session_state.seleccionados = seleccionados

    if seleccionados and st.button("🕒 Iniciar cronómetro"):
        st.session_state.cronometro_activo = True
        st.session_state.inicio_tiempo = datetime.now(tz)
        st.rerun()

# --- CRONÓMETRO DIGITAL ---
if st.session_state.cronometro_activo and st.session_state.inicio_tiempo:
    tiempo_actual = datetime.now(tz)
    transcurrido = (tiempo_actual - st.session_state.inicio_tiempo).total_seconds()
    minutos, segundos = divmod(int(transcurrido), 60)
    tiempo_formateado = f"{minutos:02d}:{segundos:02d}"
    st.markdown(f"### ⏱ Tiempo transcurrido: {tiempo_formateado}")

    # Guardar en Mongo solo si supera 2 minutos
    if transcurrido >= 120 and "guardado" not in st.session_state:
        doc = {
            "timestamp": tiempo_actual,
            "objetos": st.session_state.seleccionados,
            "duracion_segundos": int(transcurrido)
        }
        col.insert_one(doc)
        st.session_state["guardado"] = True
        st.success("✅ Sesión guardada en MongoDB.")

# --- HISTORIAL DE SESIONES ---
with st.expander("📜 Ver historial"):
    registros = list(col.find().sort("timestamp", -1))
    for i, reg in enumerate(registros):
        tiempo = reg.get("duracion_segundos", 0)
        mins, segs = divmod(tiempo, 60)
        tiempo_fmt = f"{mins:02d}:{segs:02d}"
        objetos = ", ".join(reg.get("objetos", []))
        fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"**{i+1}.** `{fecha}` – ⏱ {tiempo_fmt} – 📦 {objetos}")