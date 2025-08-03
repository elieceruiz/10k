import streamlit as st
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime
import pytz
import openai
from pymongo import MongoClient
import time

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CONEXIONES Y SECRETS ---
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["proyecto_10k"]
col = db["registro_sesiones"]
tz = pytz.timezone("America/Bogota")

# --- CARGA DE IMAGEN ---
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagen cargada", use_container_width=True)

    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode()
    img_b64_short = img_b64[:2500]  # límite para evitar excesos

    # --- DETECCIÓN DE OBJETOS ---
    if st.button("🔍 Detectar objetos"):
        with st.spinner("Analizando imagen con IA..."):
            try:
                prompt = f"""Describe brevemente solo los objetos visibles en esta imagen (usa solo palabras, no frases). Imagen en base64: {img_b64_short}"""
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Eres un asistente de visión por computadora."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.3
                )
                contenido = response.choices[0].message.content.strip()
                st.success("✅ Objetos detectados por IA.")
                st.code(contenido, language="markdown")

                objetos_detectados = [obj.strip(" .") for obj in contenido.split(",") if obj.strip()]
                st.session_state.objetos = objetos_detectados
                st.session_state.seleccion = {obj: False for obj in objetos_detectados}
                st.session_state.orden = []
                st.rerun()

            except Exception as e:
                st.error(f"Error en la detección: {e}")

# --- INTERFAZ PARA ELEGIR OBJETOS ---
if "objetos" in st.session_state and st.session_state.objetos:
    st.subheader("📦 Objetos detectados:")
    for obj in st.session_state.objetos:
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            check = st.checkbox("", key=obj)
        with col2:
            if check and obj not in st.session_state.orden:
                st.session_state.orden.append(obj)
            elif not check and obj in st.session_state.orden:
                st.session_state.orden.remove(obj)
            st.markdown(f"**{obj}**")

    if st.session_state.orden:
        st.success(f"🧩 Orden seleccionado: {', '.join(st.session_state.orden)}")

        if st.button("▶️ Iniciar sesión"):
            st.session_state.en_curso = True
            st.session_state.tiempo_inicio = time.time()
            st.session_state.tiempos_por_objeto = {obj: 0 for obj in st.session_state.orden}
            st.rerun()

# --- CRONÓMETRO ---
if st.session_state.get("en_curso", False):
    st.subheader("⏱️ Sesión en curso")
    tiempo_total = int(time.time() - st.session_state.tiempo_inicio)
    st.markdown(f"**🧭 Tiempo transcurrido:** {tiempo_total} segundos")

    for obj in st.session_state.orden:
        st.session_state.tiempos_por_objeto[obj] += 1
        st.markdown(f"- {obj}: {st.session_state.tiempos_por_objeto[obj]} segundos")

    if st.button("✅ Finalizar sesión"):
        doc = {
            "timestamp": datetime.now(tz),
            "objetos": st.session_state.orden,
            "tiempos": st.session_state.tiempos_por_objeto,
            "imagen_b64": img_b64[:1000]  # truncado para no exceder
        }
        col.insert_one(doc)
        st.success("✅ Sesión guardada.")
        for key in ["en_curso", "tiempo_inicio", "tiempos_por_objeto", "orden", "objetos", "seleccion"]:
            st.session_state.pop(key, None)
        st.rerun()

# --- HISTORIAL ---
with st.expander("📚 Historial de sesiones"):
    sesiones = list(col.find().sort("timestamp", -1))
    if sesiones:
        for reg in sesiones:
            fecha = reg.get("timestamp")
            objetos = reg.get("objetos", [])
            tiempos = reg.get("tiempos", {})
            if fecha:
                fecha = fecha.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            st.markdown(f"**📅 {fecha}**")
            for obj in objetos:
                segs = tiempos.get(obj, 0)
                st.markdown(f"- {obj}: {segs} segundos")
            st.markdown("---")
    else:
        st.info("No hay sesiones completas registradas aún.")