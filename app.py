import streamlit as st
import openai
import requests
import time
from datetime import datetime
from pymongo import MongoClient
from PIL import Image
import io

# === CONFIGURACIÓN INICIAL ===
st.set_page_config(page_title="👁️ Visión GPT – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT – Proyecto 10K")

# === SECRETS Y CLIENTES ===
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["proyecto_10k"]
col = db["sesiones_ordenamiento"]

# === FUNCIONES ===
def detectar_objetos_desde_imagen(img_bytes):
    base64_image = img_bytes.encode("base64") if isinstance(img_bytes, bytes) else img_bytes
    prompt = "Devuélveme solo los nombres de los objetos que ves en esta imagen en formato lista. Ejemplo: ['objeto 1', 'objeto 2', ...]. No expliques nada."
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente experto en visión por computadora."},
                {"role": "user", "content": f"{prompt}\nImagen (base64): {base64_image[:4000]}"}
            ],
            max_tokens=150,
        )
        contenido = response.choices[0].message.content
        lista = eval(contenido.strip())
        if isinstance(lista, list):
            return lista
        return []
    except Exception as e:
        st.warning("❌ No se pudo detectar objetos con OpenAI.")
        return []

def obtener_total_tiempo():
    sesiones = list(col.find({}))
    return sum(s.get("duracion_segundos", 0) for s in sesiones)

def convertir_formato(segundos):
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}h {minutos}m {segundos}s"

# === SUBIDA DE IMAGEN ===
imagen_cargada = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen_cargada:
    img_bytes = imagen_cargada.read()
    st.image(img_bytes, caption="Imagen cargada", use_container_width=True)

    if "objetos_detectados" not in st.session_state:
        with st.spinner("Detectando objetos en la imagen..."):
            objetos = detectar_objetos_desde_imagen(img_bytes)
            st.session_state.objetos_detectados = objetos
            st.session_state.orden_activa = None
            st.session_state.inicio = None

# === MOSTRAR OBJETOS DETECTADOS ===
if "objetos_detectados" in st.session_state and st.session_state.objetos_detectados:
    st.subheader("🎯 Objetos detectados:")
    for idx, objeto in enumerate(st.session_state.objetos_detectados):
        col1, col2 = st.columns([6, 2])
        with col1:
            st.markdown(f"- {objeto}")
        with col2:
            if st.session_state.orden_activa is None:
                if st.button(f"🕒 Iniciar", key=f"iniciar_{idx}"):
                    st.session_state.orden_activa = objeto
                    st.session_state.inicio = time.time()
            elif st.session_state.orden_activa == objeto:
                if st.button("✅ Finalizar", key=f"finalizar_{idx}"):
                    fin = time.time()
                    duracion = int(fin - st.session_state.inicio)
                    col.insert_one({
                        "objeto": objeto,
                        "inicio": datetime.fromtimestamp(st.session_state.inicio),
                        "fin": datetime.fromtimestamp(fin),
                        "duracion_segundos": duracion
                    })
                    st.success(f"✔️ Se registraron {duracion} segundos para '{objeto}'")
                    st.session_state.orden_activa = None
                    st.session_state.inicio = None
                    st.rerun()

# === CRONÓMETRO ACTIVO ===
if st.session_state.get("orden_activa") and st.session_state.get("inicio"):
    tiempo_actual = int(time.time() - st.session_state.inicio)
    st.info(f"⏳ Tiempo activo sobre '{st.session_state.orden_activa}': {convertir_formato(tiempo_actual)}")
    time.sleep(1)
    st.experimental_rerun()

# === TIEMPO ACUMULADO GLOBAL ===
total_segundos = obtener_total_tiempo()
st.subheader("📈 Tiempo acumulado hacia las 10.000 horas:")
st.success(f"🧮 Total: {convertir_formato(total_segundos)}")
progreso = total_segundos / 36000000  # 10,000 horas en segundos
st.progress(min(progreso, 1.0))

# === ENLACE AL USO DE OPENAI ===
st.markdown("[🔗 Ver uso de créditos OpenAI](https://platform.openai.com/usage)")