from datetime import datetime, timedelta
import base64
import openai
from pymongo import MongoClient
import pytz
import time
import streamlit as st
from dateutil.parser import parse

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🧠 orden-ador", layout="centered")

# Claves desde secrets
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["ordenador"]
historial_col = db["historial"]
dev_col = db["dev_tracker"]
ordenes_confirmadas_col = db["ordenes_confirmadas"]

tz = pytz.timezone("America/Bogota")

# Utilidad robusta para convertir cualquier valor a datetime local
def to_datetime_local(dt):
    if not isinstance(dt, datetime):
        dt = parse(dt)
    return dt.astimezone(tz)

# Estado base
for key, val in {
    "orden_detectados": [],
    "orden_elegidos": [],
    "orden_confirmado": False,
    "orden_asignados": [],
    "orden_en_ejecucion": None,
    "orden_timer_start": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# === FUNCIÓN DE VISIÓN GPT ===
def detectar_objetos_con_openai(imagen_bytes):
    base64_image = base64.b64encode(imagen_bytes).decode("utf-8")
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "¿Qué objetos ves en esta imagen? Solo da una lista simple."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ],
            }
        ],
        max_tokens=100
    )
    texto = response.choices[0].message.content
    objetos = [x.strip(" -•0123456789. ") for x in texto.split("\n") if x.strip()]
    return objetos

# === INTERFAZ ===
seccion = st.selectbox("¿Dónde estás trabajando?", ["💣 Desarrollo", "📸 Ordenador", "📂 Historial", "📄 Seguimiento"])

# === MÓDULO DESARROLLO
if seccion == "💣 Desarrollo":
    st.subheader("💣 Tiempo dedicado al desarrollo de orden-ador")
    evento = dev_col.find_one({"tipo": "ordenador_dev", "en_curso": True})
    if evento:
        hora_inicio = to_datetime_local(evento["inicio"])
        segundos_transcurridos = int((datetime.now(tz) - hora_inicio).total_seconds())
        st.success(f"🧠 Desarrollo en curso desde las {hora_inicio.strftime('%H:%M:%S')}")
        cronometro = st.empty()
        stop_button = st.button("⏹️ Finalizar desarrollo")
        for i in range(segundos_transcurridos, segundos_transcurridos + 100000):
            if stop_button:
                dev_col.update_one({"_id": evento["_id"]}, {"$set": {"fin": datetime.now(tz), "en_curso": False}})
                st.success("✅ Registro finalizado.")
                st.rerun()
            duracion = str(timedelta(seconds=i))
            cronometro.markdown(f"### ⏱️ Duración: {duracion}")
            time.sleep(1)
    else:
        if st.button("🟢 Iniciar desarrollo"):
            dev_col.insert_one({"tipo": "ordenador_dev", "inicio": datetime.now(tz), "en_curso": True})
            st.rerun()

# === MÓDULO ORDENADOR
elif seccion == "📸 Ordenador":
    st.subheader("📸 Ordenador con visión GPT-4o")

    orden_activa = ordenes_confirmadas_col.find_one({"estado": "en_curso"})
    if orden_activa and not st.session_state["orden_en_ejecucion"]:
        completados = orden_activa.get("items_completados", [])
        pendientes = [i for i in orden_activa["items"] if i not in completados]
        if pendientes:
            st.session_state["orden_confirmado"] = True
            st.session_state["orden_asignados"] = pendientes
            st.session_state["orden_en_ejecucion"] = pendientes[0]
            st.session_state["orden_timer_start"] = to_datetime_local(orden_activa["inicio"])
            st.warning(f"⏳ Retomando ejecución pendiente: {pendientes[0]}")

    if not st.session_state["orden_detectados"] and not st.session_state["orden_confirmado"]:
        imagen = st.file_uploader("Subí una imagen", type=["jpg", "jpeg", "png"])
        if imagen:
            with st.spinner("Detectando objetos..."):
                detectados = detectar_objetos_con_openai(imagen.read())
                st.session_state["orden_detectados"] = detectados
                st.success("Detectados: " + ", ".join(detectados))

    if st.session_state["orden_detectados"] and not st.session_state["orden_confirmado"]:
        seleccionados = st.multiselect(
            "Elegí los objetos en el orden que vas a ejecutar:",
            options=st.session_state["orden_detectados"],
            key="orden_elegidos",
            placeholder="Tocá uno por uno en orden"
        )
        if seleccionados and st.button("✔️ Confirmar orden de ejecución"):
            st.session_state["orden_asignados"] = seleccionados.copy()
            st.session_state["orden_confirmado"] = True
            st.session_state["orden_en_ejecucion"] = seleccionados[0]
            st.session_state["orden_timer_start"] = datetime.now(tz)

            ordenes_confirmadas_col.insert_one({
                "estado": "en_curso",
                "inicio": datetime.now(tz),
                "items": seleccionados,
                "items_completados": [],
            })
            st.success(f"Orden confirmada. Iniciando ejecución de: {seleccionados[0]}")
            st.rerun()

    if st.session_state["orden_en_ejecucion"]:
        actual = st.session_state["orden_en_ejecucion"]
        inicio = to_datetime_local(st.session_state["orden_timer_start"])
        segundos_transcurridos = int((datetime.now(tz) - inicio).total_seconds())

        st.success(f"🟢 Ejecutando: {actual}")
        cronometro = st.empty()
        stop_button = st.button("✅ Finalizar este ítem")

        for i in range(segundos_transcurridos, segundos_transcurridos + 100000):
            if stop_button:
                duracion = str(timedelta(seconds=i))
                historial_col.insert_one({
                    "ítem": actual,
                    "duración": duracion,
                    "timestamp": datetime.now(tz),
                })
                ordenes_confirmadas_col.update_one(
                    {"estado": "en_curso"},
                    {"$push": {"items_completados": actual}}
                )
                st.session_state["orden_asignados"].pop(0)
                if st.session_state["orden_asignados"]:
                    st.session_state["orden_en_ejecucion"] = st.session_state["orden_asignados"][0]
                    st.session_state["orden_timer_start"] = datetime.now(tz)
                else:
                    st.session_state["orden_en_ejecucion"] = None
                    st.session_state["orden_timer_start"] = None
                    st.session_state["orden_confirmado"] = False
                    st.session_state["orden_detectados"] = []
                    ordenes_confirmadas_col.update_one({"estado": "en_curso"}, {"$set": {"estado": "finalizada"}})
                st.success(f"Ítem '{actual}' finalizado en {duracion}.")
                st.rerun()
            duracion = str(timedelta(seconds=i))
            cronometro.markdown(f"### ⏱️ Tiempo transcurrido: {duracion}")
            time.sleep(1)

# === HISTORIAL
elif seccion == "📂 Historial":
    st.subheader("📂 Historial de ejecución")

    st.markdown("### 🧩 Objetos ejecutados con visión")
    registros = list(historial_col.find().sort("timestamp", -1))
    if registros:
        data_vision = []
        total = len(registros)
        for i, reg in enumerate(registros):
            fecha = to_datetime_local(reg["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            data_vision.append({
                "#": total - i,
                "Ítem": reg.get("ítem", "¿?"),
                "Duración": reg.get("duración", "N/A"),
                "Fecha": fecha
            })
        st.dataframe(data_vision, use_container_width=True)
    else:
        st.info("No hay ejecuciones registradas desde la visión.")

    st.markdown("### ⌛ Tiempo dedicado al desarrollo")
    sesiones = list(dev_col.find({"en_curso": False}).sort("inicio", -1))
    total_segundos = 0
    data_dev = []
    total = len(sesiones)
    for i, sesion in enumerate(sesiones):
        ini = to_datetime_local(sesion["inicio"])
        fin = to_datetime_local(sesion.get("fin", ini))
        segundos = int((fin - ini).total_seconds())
        total_segundos += segundos
        duracion = str(timedelta(seconds=segundos))
        data_dev.append({
            "#": total - i,
            "Inicio": ini.strftime("%Y-%m-%d %H:%M:%S"),
            "Fin": fin.strftime("%Y-%m-%d %H:%M:%S"),
            "Duración": duracion
        })
    if data_dev:
        st.dataframe(data_dev, use_container_width=True)
        st.markdown(f"**🧠 Total acumulado:** `{str(timedelta(seconds=total_segundos))}`")
    else:
        st.info("No hay sesiones de desarrollo finalizadas.")

# === SEGUIMIENTO
elif seccion == "📄 Seguimiento":
    st.subheader("📄 Seguimiento de órdenes confirmadas")
    ordenes = list(ordenes_confirmadas_col.find().sort("inicio", -1))
    if ordenes:
        data = []
        for o in ordenes:
            inicio = to_datetime_local(o["inicio"]).strftime("%Y-%m-%d %H:%M:%S")
            total = len(o["items"])
            completados = len(o.get("items_completados", []))
            estado = "🟡 En curso" if o.get("estado") == "en_curso" else "✅ Finalizado"
            data.append({
                "Estado": estado,
                "Inicio": inicio,
                "Progreso": f"{completados}/{total}",
                "Ítems": ", ".join(o["items"])
            })
        st.dataframe(data, use_container_width=True)
    else:
        st.info("No hay órdenes registradas.")
