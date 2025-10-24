import streamlit as st
import time
import requests
from io import BytesIO
from core.utils import compute_metrics  # keep import (enable if you need statistical functions)

def render_result_column(uploaded_image, config, service):
    """
    Render the result column based on the uploaded image.
    uploaded_image: UploadedFile or None
    """
    st.subheader("Result")

    if uploaded_image is None:
        st.info("Please upload an image before generating results.")
        return

    # Submit to backend/service for processing (ModelService should upload the image and return JSON containing file_id)
    with st.spinner("Submitting image and requesting backend processing..."):
        try:
            result = service.process_image(uploaded_image, config=config)
        except Exception as e:
            st.error(f"Failed to submit processing request: {e}")
            return
    st.success("Processing request submitted. Waiting for backend result...")

    # Try to find file_id in the response (adapt to different implementations)
    file_id = None
    if isinstance(result, dict):
        # Common fields: file_id, id, result.file_id
        file_id = result.get("file_id") or result.get("id")
        if not file_id:
            nested = result.get("result") or result.get("data") or {}
            if isinstance(nested, dict):
                file_id = nested.get("file_id") or nested.get("id")

    # If no file_id but result_image is returned directly (synchronous processing), display it
    if not file_id:
        if isinstance(result, dict) and result.get("result") and isinstance(result["result"], dict):
            ri = result["result"].get("result_image") or result["result"].get("image")
            if ri:
                try:
                    st.image(ri, caption="Processed result (sync)", width="stretch")
                except Exception:
                    st.write("Processing finished, but cannot preview the returned result:", ri)
                return
        if isinstance(result, bytes):
            st.image(BytesIO(result), caption="Processed result (bytes)", width="stretch")
            return
        # Fallback: display returned text/structure
        st.write(result)
        return

    # If file_id is present: poll backend /api/send/<file_id> to get final image
    backend_base = None
    if isinstance(config, dict):
        backend_base = config.get("backend_url") or config.get("api_url")
    else:
        backend_base = getattr(config, "backend_url", None) or getattr(config, "api_url", None)
    if not backend_base:
        backend_base = "http://localhost:5000"
    backend_base = backend_base.rstrip("/")

    url = f"{backend_base}/api/send/{file_id}"

    max_attempts = 30
    delay = 1.0

    # Progress bar and status text
    progress = st.progress(0)
    status = st.empty()

    for attempt in range(1, max_attempts + 1):
        # Update progress bar
        percent = int(((attempt - 1) / max_attempts) * 100)
        progress.progress(percent)

        try:
            resp = requests.get(url, timeout=8)
        except requests.RequestException as e:
            # Network/connection issue, continue retrying
            status.info(f"Waiting for result (connection issue): {e} ({attempt}/{max_attempts})")
            time.sleep(delay)
            continue

        # Backend returns 202 indicating still processing
        if resp.status_code == 202:
            time.sleep(delay)
            continue

        # Backend directly returns image content (200 + image/*)
        content_type = resp.headers.get("content-type", "")
        if resp.status_code == 200 and content_type.startswith("image"):
            try:
                # When image is received, force progress to complete
                progress.progress(100)
                status.success("Processing complete. Displaying result.")
                st.image(BytesIO(resp.content), caption="Processed result from server", width="stretch")
            except Exception:
                status.warning("Received image from backend but cannot preview it.")
                progress.progress(100)
            break

        # If JSON is returned (error or info), parse and display
        if "application/json" in content_type or resp.headers.get("content-type", "").startswith("application/json"):
            try:
                j = resp.json()
                # If backend returns status: pending with 200, continue retrying
                if isinstance(j, dict) and j.get("status") == "pending":
                    status.info(f"Backend still processing... ({attempt}/{max_attempts})")
                    time.sleep(delay)
                    continue
                # Otherwise display error/info
                status.error(f"Failed to retrieve processing result: {j}")
            except Exception:
                status.error(f"Failed to retrieve processing result, status code: {resp.status_code}")
            # Set progress to complete on error (indicates polling ended)
            progress.progress(100)
            break

        # Other cases: show error
        status.error(f"Unable to get processing result, status code: {resp.status_code}, content-type: {content_type}")
        progress.progress(100)
        break
    else:
        status.error("Timed out waiting for backend to return the processed image. Please try again later.")
        progress.progress(100)