from gevent.pywsgi import WSGIServer
from flask import Flask, redirect, request, Response, send_file
from threading import Thread
import os, importlib, schedule, time
from gevent import monkey
monkey.patch_all()

version = "3.00b"
updated_date = "Feb 1, 2025"

# Retrieve the port number from env variables
# Fallback to default if invalid or unspecified
try:
    port = int(os.environ.get("TUBI_PORT", 7777))
except:
    port = 7777


# instance of flask application
app = Flask(__name__)
provider = "tubi"
providers = {
    provider: importlib.import_module(provider).Client(),
}

url_main = f'<!DOCTYPE html>\
        <html>\
          <head>\
            <meta charset="utf-8">\
            <meta name="viewport" content="width=device-width, initial-scale=1">\
            <title>Playlist</title>\
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.1/css/bulma.min.css">\
          </head>\
          <body>\
          <section class="section">\
            <div class="container">\
              <h1 class="title is-2">\
                Playlist\
                <span class="tag">v{version}</span>\
                <span class="tag">Last Updated: {updated_date}</span>\
              </h1>\
          </div>'

@app.route("/")
def index():
    host = request.host
    body = '<div class="container">'
    for pvdr in providers:
        body_text = providers[pvdr].body_text(pvdr, host)
        body += body_text
    body += "</div></section>"
    return f"{url_main}{body}</body></html>"

@app.route("/<provider>/token")
def token(provider):
    # host = request.host
    token, error = providers[provider].token()
    if error:
        return error
    else:
        return token

@app.get("/<provider>/playlist.m3u")
def playlist(provider):
    args = request.args
    host = request.host

    m3u, error = providers[provider].generate_playlist(provider, args, host)
    if error: return error, 500
    response = Response(m3u, content_type='audio/x-mpegurl')
    return (response)

@app.get("/<provider>/channels.json")
def channels_json(provider):
        stations, err = providers[provider].channels()
        if err: return (err)
        return (stations)

@app.route("/<provider>/watch/<id>")
def watch(provider, id):
    video_url, err = providers[provider].generate_video_url(id)
    if err: return "Error", 500, {'X-Tuner-Error': err}
    if not video_url:return "Error", 500, {'X-Tuner-Error': 'No Video Stream Detected'}
    # print(f'[INFO] {video_url}')
    return (redirect(video_url))

@app.get("/<provider>/<filename>")
def epg_xml(provider, filename):
    
    ALLOWED_EPG_FILENAMES = ['epg.xml']
    ALLOWED_GZ_FILENAMES = ['epg.xml.gz']

    try:
        if filename not in ALLOWED_EPG_FILENAMES and filename not in ALLOWED_GZ_FILENAMES:
        # Check if the provided filename is allowed
        # if filename not in ALLOWED_EPG_FILENAMES:
            return "Invalid filename", 400
        error = providers[provider].epg()
        if error: return "Error in processing EPG Data", 400

        # Specify the file path based on the provider and filename
        file_path = f'{filename}'

        # Return the file without explicitly opening it
        if filename in ALLOWED_EPG_FILENAMES: 
            return send_file(file_path, as_attachment=False, download_name=file_path, mimetype='text/plain')
        elif filename in ALLOWED_GZ_FILENAMES:
            return send_file(file_path, as_attachment=True, download_name=file_path)
    except FileNotFoundError:
        return "XML file not found", 404

# Define the function you want to execute with scheduler
def epg_scheduler():
    print(f"[INFO] Running EPG Scheduler")

    try:
        error = providers[provider].epg()
        if error:
            print(f"[ERROR] EPG: {error}")
    except Exception as e:
        print(f"[ERROR] Exception in EPG Scheduler : {e}")
    print(f"[INFO] EPG Scheduler Complete")

# Define a function to run the scheduler in a separate thread
def scheduler_thread():

    # Define a task for this country
    schedule.every(1).hours.do(epg_scheduler)

    # Run the task immediately when the thread starts
    while True:
        try:
            epg_scheduler()
        except Exception as e:
            print(f"[ERROR] Error in running scheduler, retrying: {e}")
            continue  # Immediately retry

        # Continue as Scheduled
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                 print(f"[ERROR] Error in scheduler thread: {e}")
                 break # Restart the loop and rerun epg_scheduler

# Function to monitor and restart the thread if needed
def monitor_thread():
    def thread_wrapper():
        print(f"[INFO] Starting Scheduler thread")
        scheduler_thread()

    thread = Thread(target=thread_wrapper, daemon=True)
    thread.start()

    while True:
        if not thread.is_alive():
            print(f"[ERROR] Scheduler thread stopped. Restarting...")
            thread = Thread(target=thread_wrapper, daemon=True)
            thread.start()
        time.sleep(15 * 60)  # Check every 15 minutes
        print(f"[INFO] Checking scheduler thread")


if __name__ == '__main__':
    try:
        Thread(target=monitor_thread, daemon=True).start()
        print(f"[INFO] ⇨ http server started on [::]:{port}")
        WSGIServer(('', port), app, log=None).serve_forever()
    except OSError as e:
        print(str(e))
