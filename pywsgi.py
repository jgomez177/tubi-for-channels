from gevent.pywsgi import WSGIServer
from flask import Flask, redirect, request, Response, send_file
from threading import Thread
import subprocess, os, sys, importlib, schedule, time
from gevent import monkey
monkey.patch_all()

port = os.environ.get("TUBI_PORT")
if port is None:
    port = 7777
else:
    try:
        port = int(port)
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
                <span class="tag">v1.00</span>\
              </h1>\
              <p class="subtitle">\
                Last Updated: March 15, 2024\
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

@app.route("/channels/")
def channels():
    # host = request.host
    channel, error = providers[provider].channels()
    if error is not None:
        return(channel)
    else:
        return(error)

@app.get("/<provider>/playlist.m3u")
def playlist(provider):
    gracenote = request.args.get('gracenote')
    filter_stations = request.args.get('filtered')

    host = request.host

    stations, err = providers[provider].channels()
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

    if err is not None:
        return err, 500
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
    stations, err = providers[provider].channels()
    if err is not None:
        return "Error", 500, {'X-Tuner-Error': err}

    for channel in stations:
        if channel['channel-id'] == id:
            video_url = channel['url']

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
    if all(item in ALLOWED_COUNTRY_CODES for item in plex_country_list):
        for code in plex_country_list:
            error = providers[provider].epg()
            if error: print(f"{error}")


# Define a function to run the scheduler in a separate thread
def scheduler_thread():
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f"[CRITICAL] Scheduler crashed: {e}. Restarting...")
            # Restart scheduler
            schedule.clear()
            # Schedule the function to run at a given interval
            schedule.every(4).hours.do(epg_scheduler)


if __name__ == '__main__':
    # Schedule the function to run at a given interval
    schedule.every(4).hours.do(epg_scheduler)
    print("[INFO] Initialize XML File")
    error = providers[provider].epg()
    if error: 
        print(f"{error}")
    sys.stdout.write(f"⇨ http server started on [::]:{port}\n")
    try:
        # Start the scheduler thread
        thread = Thread(target=scheduler_thread)
        thread.start()
        WSGIServer(('', port), app, log=None).serve_forever()
    except OSError as e:
        print(str(e))