import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from PIL import Image
import io
import base64
import time
import pytz
import openai

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")

# --- SECRETOS ---
openai.api_key = st.secrets["openai_api_key"]
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
tz = pytz.timezone("America/Bogota")

# --- ESTADOS ---
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []
if "seleccionados" not in st.session_state:
    st.session_state.seleccionados = {}
if "cronometro_activo" not in st.session_state:
    st.session_state.cronometro_activo = False
if "inicio_sesion" not in st.session_state:
    st.session_state.inicio_sesion = None

# --- INTERFAZ ---
st.title("👁️ Visión GPT-4o – Proyecto 10K")

uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos"):
        try:
            image = Image.open(uploaded_file)
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_bytes = buffered.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

            mensajes = [
                {"role": "system", "content": "Detecta y lista los objetos visibles en esta imagen, usando palabras breves. Solo devuelve una lista JSON simple."},
                {"role": "user", "content": f"La imagen en base64 es: {img_base64}"}
            ]

            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=mensajes,
                max_tokens=300  # límite de seguridad
            )

            contenido = respuesta.choices[0].message.content.strip()
            objetos = eval(contenido) if isinstance(contenido, str) else contenido

            st.session_state.objetos_detectados = objetos
            st.session_state.seleccionados = {}

        except Exception as e:
            st.error(f"Error en la detección: {e}")

# --- MOSTRAR OBJETOS DETECTADOS ---
if st.session_state.objetos_detectados:
    st.subheader("📦 Objetos detectados:")
    for i, obj in enumerate(st.session_state.objetos_detectados, start=1):
        marcado = st.checkbox(f"{i}. {obj}", key=f"chk_{i}")
        if marcado:
            st.session_state.seleccionados[obj] = {
                "inicio": None,
                "tiempo": 0
            }

# --- CRONÓMETRO Y ORDEN ---
if st.session_state.seleccionados:
    st.subheader("⏱ Cronómetro por objeto")
    iniciar = st.button("▶️ Iniciar sesión")
    if iniciar and not st.session_state.cronometro_activo:
        st.session_state.inicio_sesion = datetime.now(tz)
        st.session_state.cronometro_activo = True
        st.rerun()

    if st.session_state.cronometro_activo:
        tiempo_total = (datetime.now(tz) - st.session_state.inicio_sesion).total_seconds()
        st.markdown(f"🧭 Tiempo total: `{int(tiempo_total)}` segundos")

        for obj in st.session_state.seleccionados.keys():
            if st.button(f"⏲ Iniciar '{obj}'"):
                st.session_state.seleccionados[obj]["inicio"] = datetime.now(tz)

            if st.session_state.seleccionados[obj]["inicio"]:
                transcurrido = (datetime.now(tz) - st.session_state.seleccionados[obj]["inicio"]).total_seconds()
                st.markdown(f"🔹 `{obj}`: `{int(transcurrido)}s`")

        if st.button("✅ Finalizar sesión"):
            final = datetime.now(tz)
            doc = {
                "timestamp": final,
                "objetos": list(st.session_state.seleccionados.keys()),
                "tiempos_individuales": {
                    k: int((datetime.now(tz) - v["inicio"]).total_seconds()) if v["inicio"] else 0
                    for k, v in st.session_state.seleccionados.items()
                },
                "tiempo_total": int(tiempo_total)
            }
            col.insert_one(doc)
            st.success("🎯 Sesión registrada")
            st.session_state.objetos_detectados = []
            st.session_state.seleccionados = {}
            st.session_state.cronometro_activo = False
            st.rerun()

# --- HISTORIAL ---
st.subheader("📚 Historial de sesiones")
registros = list(col.find().sort("timestamp", -1))
if registros:
    for reg in registros:
        fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"**🗓 Fecha:** {fecha}")
        st.markdown("**📦 Objetos:**")
        for i, obj in enumerate(reg["objetos"], start=1):
            tiempo = reg["tiempos_individuales"].get(obj, 0)
            st.markdown(f"- {i}. `{obj}` – ⏱ `{tiempo}s`")
        st.markdown(f"🧭 Tiempo total: `{reg['tiempo_total']} segundos`")
        st.markdown("---")
else:
    st.info("No hay sesiones completas registradas aún.")