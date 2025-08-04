# === IMPORTACIONES ===
import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timedelta
from PIL import Image
import base64
from io import BytesIO
import openai
import pytz
import time

# === CONFIG GENERAL ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CARGA DE SECRETOS Y CONEXIONES ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_API_KEY = st.secrets["openai_api_key"]

client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
ubicaciones_col = db["ubicaciones_migracion"]
openai.api_key = OPENAI_API_KEY
tz = pytz.timezone("America/Bogota")

# === FUNCIONES AUXILIARES ===
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

# === SESSION STATE ===
if "estado" not in st.session_state:
    st.session_state.estado = {
        "fase": "espera_foto",
        "objetos_detectados": [],
        "orden_confirmado": [],
        "imagen_b64": None,
        "imagen_para_mostrar": None,
        "objeto_en_ubicacion": None,
        "inicio_ubicacion": None
    }

estado = st.session_state.estado

# === PROGRESO TOTAL ===
total_segundos = sum(
    entrada.get("duracion_segundos", 0)
    for reg in col.find({"tiempos_zen": {"$exists": True}})
    for entrada in reg["tiempos_zen"]
)
total_horas = total_segundos / 3600
st.markdown(f"### ⏳ Progreso total: {round(total_horas, 2)} / 10.000 horas")
st.progress(min(total_horas / 10000, 1.0))

# === FLUJO MIGRACIÓN UNIFICADO ===
st.header("🧪 Migración (Detección + Ubicación + Tiempo)")
st.caption(f"🧩 Fase actual: `{estado['fase']}`")

# === FASE 1: SUBIR FOTO ===
if estado["fase"] == "espera_foto":
    archivo = st.file_uploader("📷 Toca para tomar foto", type=["jpg", "jpeg", "png"])
    if archivo:
        imagen = Image.open(archivo)
        imagen_reducida = reducir_imagen(imagen)
        imagen_b64 = convertir_imagen_base64(imagen_reducida)
        b64_img = "data:image/jpeg;base64," + imagen_b64

        with st.spinner("⏳ Detectando objetos con GPT-4o..."):
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
                    st.warning("No se detectaron objetos.")
                    st.stop()

                estado.update({
                    "fase": "seleccion_orden",
                    "imagen_b64": imagen_b64,
                    "imagen_para_mostrar": imagen_reducida,
                    "objetos_detectados": objetos
                })
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error al analizar imagen: {e}")

# === FASE 2: SELECCIÓN ORDEN ===
elif estado["fase"] == "seleccion_orden":
    st.image(estado["imagen_para_mostrar"], caption="Imagen cargada", use_container_width=True)
    seleccion = st.multiselect(
        "Selecciona los objetos en orden para ubicar:",
        options=estado["objetos_detectados"],
        default=estado["orden_confirmado"]
    )
    if seleccion and st.button("✅ Confirmar orden"):
        estado["orden_confirmado"] = seleccion.copy()
        estado["fase"] = "espera_inicio"
        st.experimental_rerun()

# === FASE 3: ESPERA INICIO UBICACIÓN ===
elif estado["fase"] == "espera_inicio":
    st.success("✅ Orden confirmado.")
    objeto_actual = st.selectbox("Selecciona el objeto a ubicar:", estado["orden_confirmado"])
    if st.button("🟢 Iniciar ubicación"):
        estado["objeto_en_ubicacion"] = objeto_actual
        estado["inicio_ubicacion"] = datetime.now(tz).isoformat()
        estado["fase"] = "ubicando"
        st.experimental_rerun()

# === FASE 4: UBICACIÓN CON CRONÓMETRO ===
elif estado["fase"] == "ubicando":
    objeto = estado["objeto_en_ubicacion"]
    inicio_dt = datetime.fromisoformat(estado["inicio_ubicacion"]).astimezone(tz)
    ahora = datetime.now(tz)
    duracion_segundos = int((ahora - inicio_dt).total_seconds())
    duracion_str = str(timedelta(seconds=duracion_segundos))

    st.success(f"📍 Ubicando: `{objeto}`")
    st.markdown(f"### 🕒 Tiempo transcurrido: `{duracion_str}`")
    lugar = st.text_input(f"📌 ¿Dónde quedó ubicado **{objeto}**?")

    st.experimental_rerun() if not lugar else None

    if lugar and st.button("⏹️ Finalizar ubicación"):
        ubicaciones_col.insert_one({
            "objeto": objeto,
            "ubicacion": lugar,
            "inicio": inicio_dt,
            "fin": ahora,
            "duracion_segundos": duracion_segundos,
            "imagen_b64": estado["imagen_b64"]
        })

        estado["orden_confirmado"].remove(objeto)
        if estado["orden_confirmado"]:
            estado["fase"] = "espera_inicio"
        else:
            st.balloons()
            st.success("🎉 Todos los objetos fueron ubicados.")
            for key in estado.keys():
                estado[key] = None if key != "fase" else "espera_foto"

        st.experimental_rerun()

# === HISTORIAL DE UBICACIONES ===
with st.expander("📚 Historial reciente de ubicaciones"):
    registros = list(ubicaciones_col.find().sort("inicio", -1).limit(10))
    for reg in registros:
        inicio = reg.get("inicio", datetime.now()).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"**🕓 {inicio}** — `{reg['objeto']}` en `{reg['ubicacion']}`")
        st.caption(f"⏱️ {round(reg.get('duracion_segundos', 0))} segundos")
        if "imagen_b64" in reg:
            st.image(Image.open(BytesIO(base64.b64decode(reg["imagen_b64"]))), width=250)