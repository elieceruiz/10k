import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timedelta
from PIL import Image
import base64
from io import BytesIO
import openai
import pytz
import time

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")
tz = pytz.timezone("America/Bogota")

# === SECRETS ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_API_KEY = st.secrets["openai_api_key"]

# === CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
openai.api_key = OPENAI_API_KEY

# === FUNCIONES ===
def convertir_imagen_base64(imagen):
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()

def reducir_imagen(imagen, max_ancho=600):
    if imagen.width > max_ancho:
        proporcion = max_ancho / imagen.width
        nuevo_tamano = (int(imagen.width * proporcion), int(imagen.height * proporcion))
        return imagen.resize(nuevo_tamano)
    return imagen

# === INICIALIZACIÓN DE ESTADOS ===
for key in ["fase", "objetos_detectados", "orden_objetos", "orden_confirmado",
            "imagen_b64", "imagen_para_mostrar", "en_progreso", "objeto_en_ubicacion",
            "inicio_ubicacion"]:
    if key not in st.session_state:
        st.session_state[key] = None if key not in ["objetos_detectados", "orden_objetos", "orden_confirmado"] else []

# === PROGRESO GLOBAL HACIA LAS 10.000 HORAS ===
total_segundos = 0
segundos_semana = 0
record_sesion = 0
primer_registro = None
inicio_semana = datetime.now(tz) - timedelta(days=7)

for reg in col.find({"tiempos_zen": {"$exists": True}}):
    ts = reg.get("timestamp")
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except:
            continue
    if not isinstance(ts, datetime):
        continue

    if not primer_registro or ts < primer_registro:
        primer_registro = ts

    for entrada in reg["tiempos_zen"]:
        duracion = entrada.get("duracion_segundos", 0)
        total_segundos += duracion
        record_sesion = max(record_sesion, duracion)
        if ts >= inicio_semana:
            segundos_semana += duracion

total_horas = total_segundos / 3600
progreso = min(total_horas / 10000, 1.0)

st.markdown(f"### ⏳ Progreso total: **{round(total_horas, 2)} / 10.000 horas**")
st.progress(progreso)

# === MIGRACIÓN DE OBJETOS CON IMAGEN ===
st.subheader("🧪 Captura con cámara")

if st.session_state["fase"] is None:
    st.session_state["fase"] = "espera_foto"

if st.session_state["fase"] == "espera_foto":
    archivo = st.file_uploader(
        label="📷 Toca para tomar foto (usa cámara móvil)",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
        key="uploader_migracion"
    )

    if archivo:
        with st.status("🌀 Procesando imagen... Esto puede tomar algunos segundos", expanded=True) as status:
            imagen = Image.open(archivo)
            st.write("🔧 Redimensionando imagen...")
            imagen_reducida = reducir_imagen(imagen)
            imagen_b64 = convertir_imagen_base64(imagen_reducida)
            b64_img = "data:image/jpeg;base64," + imagen_b64

            st.write("🤖 Enviando imagen a GPT-4o...")
            try:
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": "Detecta solo objetos visibles. Devuelve una lista clara, sin contexto extra."},
                            {"type": "image_url", "image_url": {"url": b64_img}}
                        ]}
                    ],
                    max_tokens=300
                )
                contenido = respuesta.choices[0].message.content
                objetos = [obj.strip("-• ").capitalize() for obj in contenido.split("\n") if obj.strip()]

                if not objetos:
                    st.warning("🤔 No se detectaron objetos. Intenta con una mejor imagen.")
                    st.stop()

                st.session_state["imagen_b64"] = imagen_b64
                st.session_state["imagen_para_mostrar"] = imagen
                st.session_state["objetos_detectados"] = objetos
                st.session_state["fase"] = "seleccion_orden"
                status.update(label="✅ Imagen procesada con éxito", state="complete", expanded=False)
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error al analizar imagen: {e}")
                status.update(label="❌ Error al procesar", state="error", expanded=True)

elif st.session_state["fase"] == "seleccion_orden":
    st.image(st.session_state["imagen_para_mostrar"], caption="✅ Imagen cargada", use_container_width=True)
    st.markdown("### 🧩 Selecciona los objetos que vas a ubicar (en orden)")

    seleccion = st.multiselect(
        "Toca los objetos en el orden que quieras ubicar:",
        options=st.session_state["objetos_detectados"],
        key="orden_objetos",
        placeholder="Selecciona uno por uno"
    )

    if seleccion:
        st.info(f"🗂️ Orden actual: {', '.join(seleccion)}")

    if seleccion and st.button("✅ Confirmar orden"):
        st.session_state["orden_confirmado"] = seleccion.copy()
        st.session_state["fase"] = "espera_inicio"
        st.rerun()

elif st.session_state["fase"] == "espera_inicio":
    st.success("✅ Orden confirmado.")
    objeto_actual = st.selectbox("Selecciona el objeto que vas a ubicar:", st.session_state["orden_confirmado"])
    if st.button("🟢 Iniciar ubicación"):
        st.session_state["objeto_en_ubicacion"] = objeto_actual
        st.session_state["inicio_ubicacion"] = datetime.now(tz)
        st.session_state["en_progreso"] = True
        st.session_state["fase"] = "ubicando"
        st.rerun()

elif st.session_state["fase"] == "ubicando":
    objeto = st.session_state["objeto_en_ubicacion"]
    inicio = st.session_state["inicio_ubicacion"]
    ahora = datetime.now(tz)
    segundos = int((ahora - inicio).total_seconds())
    duracion = str(timedelta(seconds=segundos))

    st.success(f"📍 Ubicando: `{objeto}`")
    st.markdown(f"### 🕒 Tiempo transcurrido: `{duracion}`")
    st.caption("⏳ Este cronómetro sigue corriendo en segundo plano...")

    lugar = st.text_input(f"📌 ¿Dónde quedó ubicado **{objeto}**?", key=f"ubicacion_{objeto}")

    if lugar and st.button("⏹️ Finalizar ubicación"):
        db["ubicaciones_migracion"].insert_one({
            "objeto": objeto,
            "ubicacion": lugar,
            "duracion_segundos": segundos,
            "inicio": inicio,
            "fin": ahora,
            "imagen_b64": st.session_state["imagen_b64"]
        })

        orden = st.session_state["orden_confirmado"]
        if objeto in orden:
            orden.remove(objeto)

        if orden:
            st.session_state["orden_confirmado"] = orden
            st.session_state["fase"] = "espera_inicio"
            st.toast(f"✅ {objeto} ubicado en {lugar} — {duracion}")
        else:
            st.success("🎉 Todos los objetos fueron ubicados.")
            st.balloons()
            for k in ["fase", "objetos_detectados", "orden_objetos", "orden_confirmado",
                      "imagen_b64", "imagen_para_mostrar", "en_progreso", "objeto_en_ubicacion", "inicio_ubicacion"]:
                st.session_state.pop(k, None)
        st.rerun()