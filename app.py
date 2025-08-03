import streamlit as st
from PIL import Image
import io
import base64
import time
import pytz
from datetime import datetime
from pymongo import MongoClient
import openai
import json
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="👁️ Proyecto 10K – Visión GPT", layout="centered")
tz = pytz.timezone("America/Bogota")

# --- SECRETS ---
MONGO_URI = st.secrets["mongo_uri"]
openai.api_key = st.secrets["openai_api_key"]

client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# --- FUNCIÓN UTILITARIA ---
def image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- DETECCIÓN GPT-4o ---
def detectar_objetos(imagen: Image.Image) -> list:
    try:
        b64 = image_to_base64(imagen)
        prompt = (
            "Enumera los objetos visibles en la imagen como una lista JSON sin explicaciones, por ejemplo: "
            '["botella", "teclado", "libreta"]. Solo responde con la lista.'
        )

        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente que detecta objetos visuales."},
                {"role": "user", "content": prompt},
                {"role": "user", "content": f"La imagen base64 es: {b64[:500]}..."}
            ],
            max_tokens=150,
            temperature=0.3
        )

        texto = respuesta.choices[0].message.content.strip()
        match = re.search(r"\[(.*?)\]", texto, re.DOTALL)
        if match:
            lista = "[" + match.group(1) + "]"
            objetos = json.loads(lista)
            return objetos if isinstance(objetos, list) else []
        return []
    except Exception as e:
        st.error(f"Error en la detección: {e}")
        return []

# --- CRONÓMETRO ---
def formato_tiempo(segundos):
    return time.strftime("%H:%M:%S", time.gmtime(segundos))

# --- INTERFAZ PRINCIPAL ---
st.title("👁️ Visión GPT-4o – Proyecto 10K")

imagen_cargada = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen_cargada:
    st.image(imagen_cargada, caption="Imagen cargada", use_container_width=True)

    img = Image.open(imagen_cargada)
    if "objetos_detectados" not in st.session_state:
        st.session_state.objetos_detectados = detectar_objetos(img)
        st.session_state.orden_seleccionado = []
        st.session_state.en_progreso = False
        st.session_state.inicio = None
        st.session_state.index_objeto = 0
        st.session_state.tiempo_objetos = {}

    if st.session_state.objetos_detectados:
        st.subheader("📦 Objetos detectados:")
        checks = {}
        for i, obj in enumerate(st.session_state.objetos_detectados):
            checks[obj] = st.checkbox(f"{obj}", key=f"check_{i}")
        
        seleccionados = [obj for obj, valor in checks.items() if valor]

        if seleccionados:
            orden = st.multiselect("📋 Orden en que serán ubicados:", seleccionados, default=seleccionados)
            if st.button("🚀 Iniciar organización") and orden:
                st.session_state.orden_seleccionado = orden
                st.session_state.en_progreso = True
                st.session_state.inicio = time.time()
                st.session_state.index_objeto = 0
                st.session_state.tiempo_objetos = {}
                st.rerun()

    if st.session_state.en_progreso and st.session_state.orden_seleccionado:
        objeto_actual = st.session_state.orden_seleccionado[st.session_state.index_objeto]
        st.markdown(f"🎯 Organizando: **{objeto_actual}**")

        tiempo_actual = int(time.time() - st.session_state.inicio)
        st.markdown(f"⏱ Tiempo transcurrido: `{formato_tiempo(tiempo_actual)}`")

        if st.button("✅ Ya fue ubicado"):
            st.session_state.tiempo_objetos[objeto_actual] = tiempo_actual
            st.session_state.index_objeto += 1
            st.session_state.inicio = time.time()

            if st.session_state.index_objeto >= len(st.session_state.orden_seleccionado):
                st.success("🎉 Todos los objetos fueron organizados.")
                doc = {
                    "objetos": st.session_state.orden_seleccionado,
                    "duraciones": st.session_state.tiempo_objetos,
                    "timestamp": datetime.now(tz)
                }
                col.insert_one(doc)
                st.session_state.en_progreso = False
                st.rerun()
            else:
                st.rerun()

st.divider()
st.subheader("📚 Historial de sesiones")

historial = list(col.find().sort("timestamp", -1))
if historial:
    for reg in historial:
        fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"**🗓️ {fecha}**")
        for i, obj in enumerate(reg["objetos"], start=1):
            t = reg["duraciones"].get(obj, 0)
            st.markdown(f"- {i}. {obj}: `{formato_tiempo(t)}`")
        st.markdown("---")
else:
    st.info("No hay sesiones registradas aún.")