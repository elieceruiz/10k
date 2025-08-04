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

# === CONFIGURACIÓN DE LA APP ===
st.set_page_config(page_title="Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CARGA DE SECRETOS ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_API_KEY = st.secrets["openai_api_key"]

# === CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
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

# === SESSION STATE INICIAL ===
for key in ["fase", "seleccionados", "modo_zen", "tareas_zen", "indice_actual", "cronometro_inicio", "tiempos_zen", "mongo_id", "imagen_cargada", "nombre_archivo", "objetos_actuales", "imagen_para_mostrar", "imagen_b64", "objeto_en_ubicacion", "inicio_ubicacion"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ["seleccionados"] else None

if "fase" not in st.session_state:
    st.session_state.fase = "espera_foto"

# === RESUMEN TOTAL DE TIEMPOS ===
total_segundos = sum(
    entrada.get("duracion_segundos", 0)
    for reg in col.find({"tiempos_zen": {"$exists": True}})
    for entrada in reg["tiempos_zen"]
)
total_horas = total_segundos / 3600
progreso = min(total_horas / 10000, 1.0)

st.markdown(f"### ⏳ Progreso total: {round(total_horas, 2)} / 10.000 horas")
st.progress(progreso)

# === INTERFAZ PRINCIPAL ===
tab_migracion, tab_historial = st.tabs(["🧪 Migración", "📚 Historial"])

# === TAB MIGRACIÓN ===
with tab_migracion:
    st.subheader("🧪 Captura con cámara")

    # === FASE 1: Subir y analizar imagen ===
    if st.session_state.fase == "espera_foto":
        archivo = st.file_uploader("📷 Toca para tomar foto", type=["jpg", "jpeg", "png"], key="file_uploader_key")
        if archivo:
            with st.status("🌀 Enviando imagen... Analizando...", expanded=True) as status:
                imagen = Image.open(archivo)
                st.write("Reduciendo imagen...")
                imagen_reducida = reducir_imagen(imagen)
                imagen_b64 = convertir_imagen_base64(imagen_reducida)
                b64_img = "data:image/jpeg;base64," + imagen_b64

                st.write("⏳ Enviando a GPT-4o...")
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

                    st.session_state.imagen_para_mostrar = imagen
                    st.session_state.imagen_b64 = imagen_b64
                    st.session_state.objetos_actuales = objetos
                    st.session_state.fase = "seleccion_orden"
                    status.update(label="✅ Imagen procesada correctamente", state="complete", expanded=False)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al analizar imagen: {e}")
                    status.update(label="❌ Fallo en análisis", state="error", expanded=True)

    # === FASE 2: Selección ordenada ===
    elif st.session_state.fase == "seleccion_orden":
        st.image(st.session_state.imagen_para_mostrar, caption="✅ Imagen cargada", use_container_width=True)
        seleccion = st.multiselect("Selecciona los objetos (en orden)", options=st.session_state.objetos_actuales, key="orden_objetos")
        if seleccion:
            st.info(f"🗂️ Orden: {', '.join(seleccion)}")
        if seleccion and st.button("✅ Confirmar orden"):
            st.session_state["orden_confirmado"] = seleccion
            st.session_state.fase = "espera_inicio"
            st.rerun()

    # === FASE 3: Espera de inicio ===
    elif st.session_state.fase == "espera_inicio":
        st.success("✅ Orden confirmado.")
        objeto_actual = st.selectbox("Selecciona el objeto a ubicar:", st.session_state["orden_confirmado"])
        if st.button("🟢 Iniciar ubicación"):
            st.session_state.objeto_en_ubicacion = objeto_actual
            st.session_state.inicio_ubicacion = datetime.now(tz)
            st.session_state.fase = "ubicando"
            st.rerun()

    # === FASE 4: Ubicando objeto ===
    elif st.session_state.fase == "ubicando":
        objeto = st.session_state.objeto_en_ubicacion
        inicio = st.session_state.inicio_ubicacion
        ahora = datetime.now(tz)
        segundos = int((ahora - inicio).total_seconds())
        duracion = str(timedelta(seconds=segundos))

        st.success(f"📍 Ubicando: `{objeto}`")
        st.markdown(f"### 🕒 Tiempo transcurrido: `{duracion}`")
        st.caption("⏳ Cronómetro en segundo plano. Finalizá cuando termines.")
        lugar = st.text_input(f"📌 ¿Dónde quedó ubicado **{objeto}**?", key=f"ubicacion_{objeto}")

        if lugar and st.button("⏹️ Finalizar ubicación"):
            db["ubicaciones_migracion"].insert_one({
                "objeto": objeto,
                "ubicacion": lugar,
                "duracion_segundos": segundos,
                "inicio": inicio,
                "fin": ahora,
                "imagen_b64": st.session_state.imagen_b64
            })
            orden = st.session_state["orden_confirmado"]
            if objeto in orden:
                orden.remove(objeto)

            if orden:
                st.session_state["orden_confirmado"] = orden
                st.session_state.fase = "espera_inicio"
                st.toast(f"✅ {objeto} ubicado en {lugar} — {duracion}")
            else:
                st.success("🎉 Todos los objetos fueron ubicados.")
                st.balloons()
                for k in ["fase", "objetos_actuales", "imagen_b64", "imagen_para_mostrar", "objeto_en_ubicacion", "inicio_ubicacion", "orden_confirmado"]:
                    st.session_state.pop(k, None)
            st.rerun()

# === TAB HISTORIAL ===
with tab_historial:
    registros = list(col.find().sort("timestamp", -1))
    if registros:
        for reg in registros:
            fecha = reg.get("timestamp", datetime.now()).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            with st.expander(f"🕓 {fecha}", expanded=False):
                if "imagen_b64" in reg:
                    st.image(Image.open(BytesIO(base64.b64decode(reg["imagen_b64"]))), width=300, caption="📸 Imagen registrada")
                st.write("📦 Objetos detectados:")
                for obj in reg.get("objetos", []):
                    st.write(f"- {obj}")
    else:
        st.info("No hay sesiones completas registradas.")