def load_uploaded_text(uploaded_file):
    """
    Read from the uploaded file-like object and decode to a UTF-8 string.
    If decoding fails, return the bytes representation as a fallback.
    """
    try:
        # uploaded_file is expected to have getvalue() that returns bytes
        return uploaded_file.getvalue().decode("utf-8")
    except Exception:
        # Fallback: return the bytes repr to avoid raising
        return str(uploaded_file.getvalue())

def compute_metrics(original, summary):
    """Simple statistics: original length, summary length, and compression ratio (original_len / summary_len)."""
    orig_len = len(original)
    summ_len = len(summary)
    # Avoid division by zero
    ratio = orig_len / summ_len if summ_len > 0 else 0
    return {"original_len": orig_len, "summary_len": summ_len, "compression_ratio": ratio}