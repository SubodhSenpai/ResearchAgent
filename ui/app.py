import json
import os
import uuid
import threading

import requests
import streamlit as st

API_BASE = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="AI Research Assistant", page_icon="[]", layout="wide")

st.title("AI Research Assistant")
st.caption("Powered by LangGraph multi-agent system")

query = st.text_area(
    "Enter your research question:",
    height=100,
    placeholder="e.g. What are the latest techniques for multi-agent coordination in LLMs?",
)

col1, col2 = st.columns([1, 1])
with col1:
    research_button = st.button("Research", type="primary", use_container_width=True)
with col2:
    cancel_button = st.button("Cancel", use_container_width=True)

if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'cancel_requested' not in st.session_state:
    st.session_state.cancel_requested = False

if cancel_button and st.session_state.session_id:
    st.session_state.cancel_requested = True
    try:
        response = requests.post(
            f"{API_BASE}/interrupt",
            json={"session_id": st.session_state.session_id},
            timeout=5
        )
        if response.status_code == 200:
            st.info("✓ Interrupt signal sent - research will stop at next checkpoint")
        else:
            st.warning(f"Could not send interrupt signal: {response.text}")
    except requests.RequestException as e:
        st.warning(f"Could not reach API to send interrupt: {e}")

if research_button:
    if not query.strip():
        st.warning("Please enter a question")
    else:
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.cancel_requested = False
        now_running = st.empty()
        trail = st.empty()

        try:
            url = f"{API_BASE}/research/stream"
            order: list[str] = []

            with requests.post(
                url,
                json={"query": query, "session_id": st.session_state.session_id},
                stream=True,
                timeout=600
            ) as resp:
                resp.raise_for_status()
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    et = event.get("type")
                    if et == "agent":
                        label = event.get("label", event.get("node", "Agent"))
                        order.append(label)
                        now_running.info(f"**Running:** {label}")
                        trail.markdown(" ▸ ".join(f"**{x}**" for x in order))

                    elif et == "result":
                        now_running.success("**Finished**")
                        data = {
                            "answer": event.get("answer", ""),
                            "messages": event.get("messages") or [],
                            "quality_score": float(event.get("quality_score") or 0.0),
                            "interrupted": event.get("interrupted", False),
                            "error": event.get("error"),
                        }
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.subheader("Answer")
                            st.markdown(data["answer"])
                        with col2:
                            score_color = "green" if data["quality_score"] >= 0.75 else "orange" if data["quality_score"] >= 0.5 else "red"
                            st.metric("Quality Score", f'{data["quality_score"]:.0%}')
                            if data["interrupted"]:
                                st.warning("⚠ Research was interrupted by user")
                            if data["error"]:
                                st.error(f"Error: {data['error']}")
                            with st.expander("Agent Log"):
                                for msg in data["messages"]:
                                    st.text(msg)

                    elif et == "error":
                        now_running.error("**Failed**")
                        st.error(event.get("detail", "Unknown error"))

        except requests.RequestException as e:
            now_running.empty()
            trail.empty()
            st.error(f"Could not reach API at {API_BASE}: {e}")

        except Exception as e:
            now_running.empty()
            trail.empty()
            st.error(f"Error: {e}")
        finally:
            st.session_state.session_id = None
            st.session_state.cancel_requested = False
