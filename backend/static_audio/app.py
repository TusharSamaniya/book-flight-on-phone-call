from flask import send_from_directory

@app.route("/static_audio/<filename>")
def serve_audio(filename):
    return send_from_directory("static_audio", filename)