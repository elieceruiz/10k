# === IMPORTS ===
import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timedelta
from PIL import Image
import base64
from io import BytesIO
import openai
import pytz
import time

# === CONFIGURACIÓN ===
st.set_page_config(page_title="Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")
tz = pytz.timezone("America/Bogota")

# === SECRETOS ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_API_KEY = st.secrets["openai_api_key"]

# === CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["ubicaciones_migracion"]
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

# === SESSION STATE ===
for key in ["fase", "objeto_en_ubicacion", "inicio_ubicacion", "imagen_b64"]:
    if key not in st.session_state:
        st.session_state[key] = None

# === PESTAÑAS ===
tab_migracion, tab_historial = st.tabs(["🧪 Migración", "📚 Historial"])

# === TAB: MIGRACIÓN ===
with tab_migracion:
    st.subheader("🧪 Captura con cámara")

    # Inicialización de estado
    estado_inicial = {
        "fase": "espera_foto",
        "objetos_detectados": [],
        "orden_objetos": [],
        "orden_confirmado": [],
        "imagen_b64": None,
        "imagen_para_mostrar": None,
        "en_progreso": False,
        "objeto_en_ubicacion": None,
        "inicio_ubicacion": None
    }

    for k, v in estado_inicial.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # === FASE 1: Subir y analizar imagen ===
    if st.session_state["fase"] == "espera_foto":
        archivo = st.file_uploader(
            label="📷 Toca para tomar foto (usa cámara móvil)",
            type=["jpg", "jpeg", "png"],
            label_visibility="collapsed",
            key="uploader_migracion"
        )

        if archivo:
            with st.spinner("🌀 Procesando imagen..."):
                imagen = Image.open(archivo)
                imagen_reducida = reducir_imagen(imagen)
                imagen_b64 = convertir_imagen_base64(imagen_reducida)
                b64_img = "data:image/jpeg;base64," + imagen_b64

                try:
                    respuesta = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": [
                                {"type": "text", "text": "Detecta solo objetos visibles. Devuelve una lista clara."},
                                {"type": "image_url", "image_url": {"url": b64_img}}
                            ]}
                        ],
                        max_tokens=300
                    )
                    contenido = respuesta.choices[0].message.content
                    objetos = [obj.strip("-• ").capitalize() for obj in contenido.split("\n") if obj.strip()]

                    if not objetos:
                        st.warning("🤔 No se detectaron objetos.")
                        st.stop()

                    st.session_state["imagen_b64"] = imagen_b64
                    st.session_state["imagen_para_mostrar"] = imagen
                    st.session_state["objetos_detectados"] = objetos
                    st.session_state["fase"] = "seleccion_orden"
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al analizar imagen: {e}")

    # === FASE 2: Selección ordenada ===
    elif st.session_state["fase"] == "seleccion_orden":
        st.image(st.session_state["imagen_para_mostrar"], caption="✅ Imagen cargada", use_container_width=True)
        st.markdown("### 🧩 Selecciona los objetos en el orden que vas a ubicar")

        seleccion = st.multiselect(
            "Toca en orden los objetos:",
            options=st.session_state["objetos_detectados"],
            default=st.session_state["orden_objetos"],
            key="orden_objetos"
        )

        if seleccion:
            st.session_state["orden_objetos"] = seleccion
            st.info(f"🗂️ Orden actual: {', '.join(seleccion)}")

        if seleccion and st.button("✅ Confirmar orden"):
            st.session_state["orden_confirmado"] = seleccion.copy()
            st.session_state["fase"] = "espera_inicio"
            st.rerun()

    # === FASE 3: Espera inicio ===
    elif st.session_state["fase"] == "espera_inicio":
        st.success("✅ Orden confirmado.")
        objeto_actual = st.selectbox("Selecciona el objeto que vas a ubicar:", st.session_state["orden_confirmado"])
        if st.button("🟢 Iniciar ubicación"):
            st.session_state["objeto_en_ubicacion"] = objeto_actual
            st.session_state["inicio_ubicacion"] = datetime.now(tz)
            st.session_state["en_progreso"] = True
            st.session_state["fase"] = "ubicando"
            st.rerun()

    # === FASE 4: Ubicando ===
    elif st.session_state["fase"] == "ubicando":
        objeto = st.session_state["objeto_en_ubicacion"]
        inicio = st.session_state["inicio_ubicacion"]
        ahora = datetime.now(tz)
        duracion_segundos = int((ahora - inicio).total_seconds())
        duracion = str(timedelta(seconds=duracion_segundos))

        st.success(f"📍 Ubicando: `{objeto}`")
        st.markdown(f"### 🕒 Tiempo transcurrido: `{duracion}`")

        lugar = st.text_input(f"📌 ¿Dónde quedó ubicado **{objeto}**?", key=f"ubicacion_{objeto}")
        if lugar and st.button("⏹️ Finalizar ubicación"):
            db["ubicaciones_migracion"].insert_one({
                "objeto": objeto,
                "ubicacion": lugar,
                "duracion_segundos": duracion_segundos,
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
                for k in estado_inicial.keys():
                    st.session_state.pop(k, None)

            st.rerun()

# === TAB HISTORIAL ===
with tab_historial:
    registros = list(col.find().sort("inicio", -1))
    if registros:
        for reg in registros:
            fecha = reg["inicio"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            with st.expander(f"🕓 {fecha} — {reg.get('objeto', 'Sin nombre')}"):
                if "imagen_b64" in reg:
                    st.image(Image.open(BytesIO(base64.b64decode(reg["imagen_b64"]))), width=300)

                st.write(f"🧱 Objeto: {reg.get('objeto')}")
                st.write(f"📌 Ubicación: {reg.get('ubicacion', '—')}")
                st.write(f"⏱️ Duración: {round(reg.get('duracion_segundos', 0))} segundos")
    else:
        st.info("📭 No hay registros aún.")