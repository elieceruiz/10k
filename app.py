import streamlit as st
from PIL import Image
from datetime import datetime
import time
import io
import pytz
from pymongo import MongoClient
import openai
import base64

# --- CONFIG ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- SECRETS ---
openai.api_key = st.secrets["openai_api_key"]
MONGO_URI = st.secrets["mongo_uri"]

# --- MONGO ---
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# --- ZONA HORARIA ---
tz = pytz.timezone("America/Bogota")

# --- ESTADO DE SESIÓN ---
if "in_session" not in st.session_state:
    st.session_state.in_session = False
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "objetos_seleccionados" not in st.session_state:
    st.session_state.objetos_seleccionados = []
if "cronometros" not in st.session_state:
    st.session_state.cronometros = {}
if "image_data" not in st.session_state:
    st.session_state.image_data = None
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []

# --- SUBIDA DE IMAGEN ---
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen:
    img = Image.open(imagen)
    st.image(img, caption="Imagen cargada", use_container_width=True)
    st.session_state.image_data = imagen.read()

    if st.button("🔍 Detectar objetos"):
        try:
            # Convertimos a base64 pero sin pasarnos de tokens
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode()

            prompt = "Detecta solo los objetos que se ven en la imagen. Da una lista breve sin descripciones largas. Ejemplo: 'Botella', 'Portátil', 'Cable USB'"

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un experto en visión por computador."},
                    {"role": "user", "content": f"{prompt}\n\nEsta es la imagen codificada en base64:\n{img_b64[:4000]}"}
                ],
                max_tokens=200,
                temperature=0
            )

            contenido = response.choices[0].message.content.strip()
            objetos = [obj.strip(" -•\n") for obj in contenido.split("\n") if obj.strip()]
            st.session_state.objetos_detectados = objetos
            st.session_state.objetos_seleccionados = []

            if objetos:
                st.success("✅ Objetos detectados por IA.")
            else:
                st.warning("❌ No se detectaron objetos.")
        except Exception as e:
            st.error(f"Error en la detección: {e}")

# --- LISTADO DE OBJETOS DETECTADOS ---
if st.session_state.objetos_detectados and not st.session_state.in_session:
    st.subheader("📦 Objetos detectados:")
    seleccionados = []
    for obj in st.session_state.objetos_detectados:
        if st.checkbox(obj, key=obj):
            seleccionados.append(obj)

    st.session_state.objetos_seleccionados = seleccionados

    if seleccionados:
        if st.button("🕒 Iniciar sesión de práctica"):
            st.session_state.start_time = datetime.now(tz)
            st.session_state.in_session = True
            st.session_state.cronometros = {obj: {"inicio": time.time(), "duracion": 0} for obj in seleccionados}
            st.rerun()

# --- SESIÓN ACTIVA ---
if st.session_state.in_session:
    st.subheader("⏱️ Cronómetro en curso:")
    tiempo_actual = time.time()
    total = 0
    for obj in st.session_state.objetos_seleccionados:
        inicio = st.session_state.cronometros[obj]["inicio"]
        duracion = int(tiempo_actual - inicio)
        st.session_state.cronometros[obj]["duracion"] = duracion
        total += duracion
        st.text(f"{obj}: {duracion} segundos")

    st.text(f"🧭 Tiempo total: {total} segundos")

    if st.button("🛑 Finalizar sesión"):
        doc = {
            "timestamp": st.session_state.start_time,
            "objetos": st.session_state.objetos_seleccionados,
            "duraciones": {obj: st.session_state.cronometros[obj]["duracion"] for obj in st.session_state.objetos_seleccionados},
            "duracion_total": total,
            "imagen": st.session_state.image_data
        }
        col.insert_one(doc)
        st.success("✅ Sesión guardada.")
        st.session_state.in_session = False
        st.session_state.start_time = None
        st.session_state.cronometros = {}
        st.session_state.objetos_detectados = []
        st.session_state.objetos_seleccionados = []
        st.session_state.image_data = None
        st.rerun()

# --- HISTORIAL ---
st.divider()
st.subheader("📚 Historial de sesiones")

registros = list(col.find().sort("timestamp", -1).limit(5))
if registros:
    for reg in registros:
        try:
            fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            st.markdown(f"🗓️ Fecha: {fecha}")
            st.markdown(f"⏳ Tiempo total: {reg['duracion_total']} segundos")
            st.markdown(f"📦 Objetos:")
            for i, obj in enumerate(reg["objetos"], start=1):
                dur = reg["duraciones"].get(obj, 0)
                st.markdown(f"- {i}. {obj}: {dur} segundos")
            st.markdown("---")
        except:
            continue
else:
    st.info("No hay sesiones completas registradas aún.")