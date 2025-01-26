from gevent.pywsgi import WSGIServer
from flask import Flask, redirect, request, Response, send_file
from threading import Thread
import os, importlib, schedule, time
from gevent import monkey
monkey.patch_all()

version = "2.03"
updated_date = "Jan. 26, 2025"

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

url = f'<!DOCTYPE html>\
        <html>\
          <head>\
            <meta charset="utf-8">\
            <meta name="viewport" content="width=device-width, initial-scale=1">\
            <title>{provider.capitalize()} Playlist</title>\
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.1/css/bulma.min.css">\
            <style>\
              ul{{\
                margin-bottom: 10px;\
              }}\
            </style>\
          </head>\
          <body>\
          <section class="section">\
            <div class="container">\
              <h1 class="title">\
                {provider.capitalize()} Playlist\
                <span class="tag">v{version}</span>\
              </h1>\
              <p class="subtitle">\
                Last Updated: {updated_date}\
              '

@app.route("/")
def index():
    host = request.host
    ul = f'<p class="subtitle"></p><ul>'
    pl = f"http://{host}/{provider}/playlist.m3u"
    ul += f"<li>{provider.upper()}: <a href='{pl}'>{pl}</a></li>\n"
    pl = f"http://{host}/{provider}/playlist.m3u?gracenote=include"
    ul += f"<li>{provider.upper()} Gracenote Playlist: <a href='{pl}'>{pl}</a></li>\n"
    pl = f"http://{host}/{provider}/playlist.m3u?gracenote=exclude"
    ul += f"<li>{provider.upper()} EPG Only Playlist: <a href='{pl}'>{pl}</a></li>\n"
    pl = f"http://{host}/{provider}/epg.xml"
    ul += f"<li>{provider.upper()} EPG: <a href='{pl}'>{pl}</a></li>\n"
    pl = f"http://{host}/{provider}/epg.xml.gz"
    ul += f"<li>{provider.upper()} EPG GZ: <a href='{pl}'>{pl}</a></li>\n"
    ul += f"<br>\n"

    return f"{url}<ul>{ul}</ul></div></section></body></html>"

@app.route("/<provider>/token/")
def token(provider):
    # host = request.host
    token = providers[provider].token()
    if token is None:
        return("Using Anonymous Access")
    else:
        return token

@app.get("/<provider>/playlist.m3u")
def playlist(provider):
    gracenote = request.args.get('gracenote')
    filter_stations = request.args.get('filtered')

    host = request.host

    stations, err = providers[provider].channels()
    if err: return err, 500
    # Filter out Hidden items or items without Hidden Attribute
    tmsid_stations = list(filter(lambda d: d.get('tmsid'), stations))
    no_tmsid_stations = list(filter(lambda d: d.get('tmsid', "") == "" or d.get('tmsid') is None, stations))

    if 'unfiltered' not in request.args and gracenote == 'include':
        data_group = tmsid_stations
    elif  'unfiltered' not in request.args and gracenote == 'exclude':
        data_group = no_tmsid_stations
    else:
        data_group = stations


    stations = sorted(stations, key = lambda i: i.get('name', ''))

    if err: return err, 500
    m3u = "#EXTM3U\r\n\r\n"
    for s in data_group:
        m3u += f"#EXTINF:-1 channel-id=\"{provider}-{s.get('channel-id')}\""
        m3u += f" tvg-id=\"{s.get('channel-id')}\""
        m3u += f" tvg-chno=\"{''.join(map(str, s.get('number', [])))}\"" if s.get('number') else ""
        m3u += f" group-title=\"{''.join(map(str, s.get('group', [])))}\"" if s.get('group') else ""
        m3u += f" tvg-logo=\"{''.join(map(str, s.get('logo', [])))}\"" if s.get('logo') else ""
        m3u += f" tvg-name=\"{s.get('call_sign')}\"" if s.get('call_sign') else ""
        if gracenote == 'include':
            m3u += f" tvg-shift=\"{s.get('time_shift')}\"" if s.get('time_shift') else ""
            m3u += f" tvc-guide-stationid=\"{s.get('tmsid')}\"" if s.get('tmsid') else ""
        m3u += f",{s.get('name') or s.get('call_sign')}\n"
        # m3u += f"{s.get('url')}\n\n"
        m3u += f"http://{host}/{provider}/watch/{s.get('channel-id')}\n\n"

    response = Response(m3u, content_type='audio/x-mpegurl')
    return (response)

@app.get("/<provider>/channels.json")
def channels_json(provider):
        stations, err = providers[provider].channels()
        if err: return (err)
        # response = Response(stations)
        # print(stations)
        return (stations)

@app.get("/<provider>/epg.json")
def epg_json(provider):
        epg_data, err = providers[provider].epg_json()
        if err: return (err)
        # response = Response(stations)
        # print(stations)
        return (epg_data)

@app.get("/<provider>/clear")
def channels_clear(provider):
        err = providers[provider].clear_data()
        if err: return (err)
        # response = Response(stations)
        # print(stations)
        return ("Data Cleared")

@app.route("/<provider>/watch/<id>")
def watch(provider, id):
    video_url = ''

    stations, err = providers[provider].channels()
    if err is not None:
        return "Error", 500, {'X-Tuner-Error': err}

    for channel in stations:
        if channel['channel-id'] == id:
            video_url = channel['url']

    if video_url == '':
        return "Error", 500, {'X-Tuner-Error': 'Video Stream Not Found'}

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
        stations, err = providers[provider].channels()
        if err: print(f"[ERROR] Channels: {error}")
        error = providers[provider].epg()
        if error:
            print(f"[ERROR] EPG: {error}")
    except Exception as e:
        print(f"[ERROR] Exception in EPG Scheduler : {e}")
    print(f"[INFO] EPG Scheduler Complete")

# Define a function to run the scheduler in a separate thread
def scheduler_thread():

    # Define a task for this country
    schedule.every(2).hours.do(epg_scheduler)

    # Run the task immediately when the thread starts
    try:
        epg_scheduler()
    except Exception as e:
        print(f"[ERROR] Error running initial task for: {e}")

    # Continue as Scheduled
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
             print(f"[ERROR] Error in scheduler thread: {e}")

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
        # print(f"[INFO] Checking scheduler thread for {country_code}")


if __name__ == '__main__':
    try:
        Thread(target=monitor_thread, daemon=True).start()
        print(f"⇨ http server started on [::]:{port}")
        WSGIServer(('', port), app, log=None).serve_forever()
    except OSError as e:
        print(str(e))
