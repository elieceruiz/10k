import streamlit as st
from datetime import datetime, timedelta
import base64
import openai
from pymongo import MongoClient
import pytz
from streamlit_javascript import st_javascript
import time

# === CONFIGURACIÓN ===
st.set_page_config(page_title="🧠 orden-ador", layout="centered")
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["ordenador"]
historial_col = db["historial"]
dev_col = db["dev_tracker"]
tz = pytz.timezone("America/Bogota")

# === ESTADO BASE ===
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

# === RECUPERAR CRONÓMETRO SI SE REINICIÓ LA APP ===
if not st.session_state["orden_timer_start"]:
    en_curso = historial_col.find_one({"en_ejecucion": True})
    if en_curso:
        st.session_state["orden_en_ejecucion"] = en_curso["ítem"]
        st.session_state["orden_timer_start"] = en_curso["timestamp"]

# === VISIÓN: DETECTAR OBJETOS ===
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
seccion = st.selectbox("¿Dónde estás trabajando?", ["💣 Desarrollo", "📸 Ordenador", "📂 Historial"])

# === OPCIÓN 1: DESARROLLO
if seccion == "💣 Desarrollo":
    st.subheader("💣 Tiempo dedicado al desarrollo de orden-ador")
    evento = dev_col.find_one({"tipo": "ordenador_dev", "en_curso": True})
    if evento:
        hora_inicio = evento["inicio"].astimezone(tz)
        segundos_transcurridos = int((datetime.now(tz) - hora_inicio).total_seconds())
        st.success(f"🧠 Desarrollo en curso desde las {hora_inicio.strftime('%H:%M:%S')}")
        duracion = str(timedelta(seconds=segundos_transcurridos))
        st.markdown(f"### ⏱️ Duración: `{duracion}`")
        if st.button("⏹️ Finalizar desarrollo"):
            dev_col.update_one({"_id": evento["_id"]}, {"$set": {"fin": datetime.now(tz), "en_curso": False}})
            st.success("✅ Registro finalizado.")
            st.rerun()
        time.sleep(1)
        st.rerun()
    else:
        if st.button("🟢 Iniciar desarrollo"):
            dev_col.insert_one({"tipo": "ordenador_dev", "inicio": datetime.now(tz), "en_curso": True})
            st.rerun()

# === OPCIÓN 2: ORDENADOR
elif seccion == "📸 Ordenador":
    st.subheader("📸 Ordenador con visión GPT-4o")

    # Paso 1: subir imagen
    if not st.session_state["orden_detectados"]:
        imagen = st.file_uploader("Subí una imagen", type=["jpg", "jpeg", "png"])
        if imagen:
            with st.spinner("Detectando objetos..."):
                detectados = detectar_objetos_con_openai(imagen.read())
                st.session_state["orden_detectados"] = detectados
                st.success("Detectados: " + ", ".join(detectados))

    # Paso 2: seleccionar orden
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
            st.success("Orden confirmado. Empezá a ejecutar cada ítem.")
            st.rerun()

    # Paso 3: ejecutar ítems
    if st.session_state["orden_confirmado"] and not st.session_state["orden_en_ejecucion"]:
        if st.session_state["orden_asignados"]:
            actual = st.session_state["orden_asignados"][0]
            st.subheader(f"🎯 Enfoque actual: **{actual}**")
            if st.button("🚀 Iniciar ejecución"):
                inicio = datetime.now(tz)
                st.session_state["orden_en_ejecucion"] = actual
                st.session_state["orden_timer_start"] = inicio
                historial_col.insert_one({
                    "ítem": actual,
                    "timestamp": inicio,
                    "en_ejecucion": True
                })
                st.rerun()
        else:
            st.success("✅ Todos los ítems fueron ejecutados.")
            for key in ["orden_detectados", "orden_elegidos", "orden_confirmado",
                        "orden_asignados", "orden_en_ejecucion", "orden_timer_start"]:
                st.session_state[key] = [] if isinstance(st.session_state[key], list) else None
            st.rerun()

    # Paso 4: cronómetro fluido
    if st.session_state["orden_en_ejecucion"]:
        actual = st.session_state["orden_en_ejecucion"]
        inicio = st.session_state["orden_timer_start"]
        st.success(f"🟢 Ejecutando: {actual}")
        st.markdown("### ⏱️ Tiempo transcurrido:")
        st.markdown('<h2 id="cronovisor">00:00:00</h2>', unsafe_allow_html=True)
        js_code = f"""
        const startTime = new Date("{inicio.isoformat()}").getTime();
        setInterval(() => {{
            const now = new Date().getTime();
            const elapsed = now - startTime;
            const totalSeconds = Math.floor(elapsed / 1000);
            const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
            const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
            const seconds = String(totalSeconds % 60).padStart(2, '0');
            document.getElementById("cronovisor").innerText = `\${hours}:\${minutes}:\${seconds}`;
        }}, 1000);
        """
        st_javascript(js_code)

        if st.button("✅ Finalizar este ítem"):
            ahora = datetime.now(tz)
            duracion = str(timedelta(seconds=int((ahora - inicio).total_seconds())))
            historial_col.update_one(
                {"ítem": actual, "en_ejecucion": True},
                {"$set": {
                    "duración": duracion,
                    "timestamp_fin": ahora,
                    "en_ejecucion": False
                }}
            )
            st.session_state["orden_asignados"].pop(0)
            st.session_state["orden_en_ejecucion"] = None
            st.session_state["orden_timer_start"] = None
            st.success(f"Ítem '{actual}' finalizado en {duracion}.")
            st.rerun()

# === OPCIÓN 3: HISTORIAL
elif seccion == "📂 Historial":
    st.subheader("📂 Historial de ejecución")

    st.markdown("### 🧩 Objetos ejecutados con visión")
    registros = list(historial_col.find({"en_ejecucion": False}).sort("timestamp_fin", -1))
    if registros:
        data_vision = []
        total = len(registros)
        for i, reg in enumerate(registros):
            fecha = reg["timestamp_fin"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            data_vision.append({
                "#": total - i,
                "Ítem": reg["ítem"],
                "Duración": reg["duración"],
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
        ini = sesion["inicio"].astimezone(tz)
        fin = sesion.get("fin", ini).astimezone(tz)
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