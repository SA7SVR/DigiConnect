"""Audio device discovery (sounddevice). Returns empty lists, never raises."""
def list_devices():
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        return ([d["name"] for d in devs if d["max_input_channels"] > 0], [d["name"] for d in devs if d["max_output_channels"] > 0], "")
    except Exception as e:  # PortAudio missing, no hardware, headless
        return ([], [], f"Audio devices unavailable ({e.__class__.__name__})")
