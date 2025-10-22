import streamlit as st
import time
from core.utils import compute_metrics  # keep import (enable if you need statistical functions)

def render_result_column(uploaded_image, config, service):
    """
    Render the result column based on the uploaded image.
    uploaded_image: UploadedFile or None
    """
    st.subheader("Result")

    # Previously used text-based check; now check based on image presence
    can_generate = uploaded_image is not None

    if not can_generate:
        st.info("Please upload an image before generating results.")
        return

    # Example: display the image and call the service to process it (adjust according to actual project API)
    try:
        st.image(uploaded_image, caption="Preview of the image to be processed", use_container_width=True)
    except Exception:
        st.warning("Unable to preview the image, but will attempt to process it.")

    # Call model/service to process the image (adjust to actual model_service interface)
    with st.spinner("Processing image..."):
        result = service.process_image(uploaded_image, config=config)
    st.success("Processing complete")
    st.write(result)