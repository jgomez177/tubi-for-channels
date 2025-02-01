import json, os, uuid, threading, requests, time, base64, binascii, pytz, gzip, csv, os
import xml.etree.ElementTree as ET
from datetime import datetime

class Client:
    def __init__(self):
        self.lock = threading.Lock()
        self.load_device()
        self.generate_verifier()
        self.user = os.environ.get("TUBI_USER")
        self.passwd = os.environ.get("TUBI_PASS")
        self.token_sessionAt = time.time()
        self.token_expires_in = 0
        self.tokenResponse = None
        self.sessionAt = 0
        self.session_expires_in = 0
        self.channel_list = []

        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': 'https://tubitv.com',
            'priority': 'u=1, i',
            'referer': 'https://tubitv.com/',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }


    def is_uuid4(self, string):
        try:
            uuid_obj = uuid.UUID(string, version=4)
            return str(uuid_obj) == string
        except ValueError:
            return False

    def isTimeExpired(self, sessionAt, age):
        # print ((time.time() - sessionAt), age)
        return ((time.time() - sessionAt) >= age)

    def load_device(self):
        device_file = "tubi-device.json"
        try:
            with open(device_file, "r") as f:
                device_id = json.load(f)
        except FileNotFoundError:
            device_id = str(uuid.uuid4())
            with open(device_file, "w") as f:
                json.dump(device_id, f)
            print(f"[INFO] Device ID Generated")
        is_valid_uuid4 = self.is_uuid4(device_id)
        if not is_valid_uuid4:
            print(f"[WARNING] Device ID Not Valid: {device_id}")
            print(f"[WARNING] Reload Device ID")
            os.remove(device_file)
            self.load_device()
        else:
            # print(f"[INFO] Device ID: {device_id}")
            with self.lock:
                self.device_id = device_id

    def call_token_api(self, json_data, local_headers, isAnonymous):
        if isAnonymous:
            url = 'https://account.production-public.tubi.io/device/anonymous/token'
        else:
            url = 'https://account.production-public.tubi.io/user/login'

        error = None
        # print(json.dumps(json_data, indent = 2))
        local_token_sessionAt = self.token_sessionAt
        local_token_expires_in = self.token_expires_in
        tokenResponse = self.tokenResponse
        
        if self.isTimeExpired(local_token_sessionAt, local_token_expires_in) or (tokenResponse is None):
            print("[INFO] Update Token via API Call")
            print("[INFO] Updating Token Session")
            local_token_sessionAt = time.time()
            try:
                session = requests.Session()
                tokenResponse = session.post(url, json=json_data, headers=local_headers)
            except requests.ConnectionError as e:
                error = f"Connection Error. {str(e)}"
            finally:
                # print(error)
                # print(data)
                print('[INFO] Close the Token API session')
                session.close()
        else:
            print("[INFO] Return Token")
        
        if error:
            print(error)
            return None, None, None, error

        if tokenResponse.status_code != 200:
            print(f"HTTP: {tokenResponse.status_code}: {tokenResponse.text}")
            return None, None, None, tokenResponse.text
        else:
            resp = tokenResponse.json()

        # print(json.dumps(resp, indent = 2))
        with self.lock:
            self.tokenResponse = tokenResponse
        access_token = resp.get('access_token', None)
        local_token_expires_in = resp.get('expires_in', local_token_expires_in)        
        print(f"[INFO] Token Expires IN: {local_token_expires_in}")

        return (access_token, local_token_sessionAt, local_token_expires_in, error)

    def use_signin_creds(self, local_user, local_passwd):
        local_device_id = self.device_id
        local_headers = self.headers.copy()

        json_data = {
            'type': 'email',
            'platform': 'web',
            'device_id': local_device_id,
            'credentials': {
                'email': local_user,
                'password': local_passwd
            },
            'errorLog': False,
        }
        return self.call_token_api(json_data, local_headers, False)


    def generate_challenge_text(self):
        random_bytes = os.urandom(32)  # Generate 32 random bytes
        challenge_text = base64.urlsafe_b64encode(random_bytes).rstrip(b'=').decode('utf-8')
        return challenge_text

    def generate_verifier(self):
        random_bytes = os.urandom(16)  # Generate 16 random bytes
        verifier = binascii.hexlify(random_bytes).decode('utf-8')
        with self.lock:
            self.verifier = verifier
        return None

    def generate_anonymous_token(self, device_id, id):
        error = None
        verifier = self.verifier
        local_headers = self.headers.copy()

        # params = {'X-Tubi-Algorithm': 'TUBI-HMAC-SHA256'}

        json_data = {
            'verifier': verifier,
            'id': id,
            'platform': 'web',
            'device_id': device_id,
            }
        
        return self.call_token_api(json_data, local_headers, True)


    def use_anonymous_creds(self):
        # print('[INFO] Using anonymous credentials')
        error = '[ERROR] Anonymous Credentials Not Functioning. Please use username/password credentials'
        if error:
            print(error)
            os._exit(-999)  

        challenge = self.generate_challenge_text()
        device_id = self.device_id
        headers = self.headers.copy()
        json_data = {
            'challenge': challenge,
            'version': '1.0.0',
            'platform': 'web',
            'device_id': device_id,
            }

        try:
            session = requests.Session()
            response = session.post('https://account.production-public.tubi.io/device/anonymous/signing_key', headers=headers, json=json_data)
        except requests.ConnectionError as e:
            error = f"Connection Error. {str(e)}"
        finally:
            session.close()

        # print(f"HTTP: {response.status_code}: {response.text}")

        if error:
            print(error)
            return None, None, None, error

        if response.status_code != 200:
            print(f"HTTP: {response.status_code}: {response.text}")
            return None, None, None, response.text
    
        resp = response.json()
        id = resp.get('id')
        key = resp.get('key')
        # print(id)
        return (self.generate_anonymous_token(device_id, id))


    def token(self):
        local_user = self.user
        local_passwd = self.passwd
        error = None

        if local_user is None or local_passwd is None:
            access_token, local_token_sessionAt, local_token_expires_in, error = self.use_anonymous_creds()
            if error:
                print(f'[ERROR] Error in use_anonymous_creds {error}')
                return None, error
            with self.lock:
                self.access_token = access_token
                self.token_expires_in = local_token_expires_in
                self.token_sessionAt = local_token_sessionAt
        else:
            access_token, local_token_sessionAt, local_token_expires_in, error = self.use_signin_creds(local_user, local_passwd)
            if error:
                print(f'[ERROR] Error in use_signin_creds {error}')
                return None, error
            with self.lock:
                self.access_token = access_token
                self.token_expires_in = local_token_expires_in
                self.token_sessionAt = local_token_sessionAt

        return access_token, error

    def update_tmsid(self, channel_dict):
        tubi_tmsid_url = "https://raw.githubusercontent.com/jgomez177/tubi-for-channels/main/tubi_tmsid.csv"
        tubi_custom_tmsid = 'tubi_data/tubi_custom_tmsid.csv'

        tmsid_dict = {}
        tmsid_custom_dict = {}

        # Fetch the CSV file from the URL
        with requests.Session() as session:
            response = session.get(tubi_tmsid_url)
            # print(response.text)

        # Check if request was successful
        if response.status_code == 200:
            # Read in the CSV data
            # print("[INFO] Read in file data from github")
            reader = csv.DictReader(response.text.splitlines())
        else:
            # Use local cache instead
            print("[NOTIFICATION] Failed to fetch the CSV file. Status code:", response.status_code)
            print("[NOTIFICATION] Using local cached file.")
            with open('tubi_tmsid.csv', mode='r') as file:
                reader = csv.DictReader(file)
        for row in reader:
            tmsid_dict[row['id']] = row

        if os.path.exists(tubi_custom_tmsid):
            # File exists, open it
            with open(tubi_custom_tmsid, mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    tmsid_custom_dict[row['id']] = row

        tmsid_dict.update(tmsid_custom_dict)

       # print(json.dumps(tmsid_dict, indent=2))

        for listing in tmsid_dict:
            cid = listing
            tmsid = tmsid_dict[listing].get('tmsid')
            time_shift = tmsid_dict[listing].get('time_shift')
    
            if cid in channel_dict:
                name = channel_dict[cid].get('name')
                old_tmsid = channel_dict[cid].get('tmsid')
                print(f"[INFO] Updating {name} with {tmsid} from {old_tmsid}")
                channel_dict[cid].update({'tmsid': tmsid}) # Updates channel_list in place
                if time_shift:
                    print(f"[INFO] Add Time Shift")
                    channel_dict[cid].update({'time_shift': time_shift}) # Updates channel_list in place

        return 



    def channels(self):
        channel_list = self.channel_list
        sessionAt = self.sessionAt
        session_expires_in = self.session_expires_in

        if not(self.isTimeExpired(sessionAt, session_expires_in)) and channel_list:
            print("[INFO] Reading channel id list cache")
            return channel_list, None

        local_headers = self.headers
        local_device_id = self.device_id
        bearer, error = self.token()
        if error: return None, error
        local_headers.update({'authorization': f'Bearer {bearer}',
                              'x-tubi-mode': 'all',
                              'x-tubi-platform': 'web'
                              })

        params = {'mode': 'tubitv_us_linear',
                  'platform': 'web',
                  'device_id': local_device_id,
                 }

        url = 'https://tensor-cdn.production-public.tubi.io/api/v2/epg'

        # print(json.dumps(local_headers, indent =2))
        sessionAt = time.time()

        try:
            session = requests.Session()
            epgResponse = session.get(url, params=params, headers=local_headers)
        except requests.ConnectionError as e:
            error = f"Connection Error. {str(e)}"
        finally:
            print('[INFO] Close the EPG API session')
            session.close()

        if error:
            print (f'[ERROR] {error}')
            return None, error
        
        if epgResponse.status_code != 200:
            print(f"[ERROR] HTTP: {epgResponse.status_code}: {epgResponse.text}")
            return None, epgResponse.text
        else:
            resp = epgResponse.json()

        #print(json.dumps(resp, indent=2))

        if 'alert' in resp:
            print(f'[WARNING] {resp.get("alert")}')

        containers = resp.get('containers')
        if containers is None:
            return None, f'[ERROR] No containers found'
        
        # print(json.dumps(containers, indent=2)) 

        skip_slugs = ['favorite_linear_channels', 'recommended_linear_channels', 'featured_channels', 'recently_added_channels']

        channel_id_list = [content for item in containers if item['container_slug'] not in skip_slugs for content in item["contents"]]
        channel_id_list = list(set(channel_id_list))
        #print(f'[INFO] Number of streams available: {len(channel_id_list)}')


        groups = {}
        for elem in containers:
            if elem["container_slug"] not in skip_slugs:
                groups.update({elem['name']: elem['contents']})

        # print(json.dumps(groups, indent=2))

        contents = resp.get('contents')
        channel_list = [{'channel-id': elem,
                         'name': contents.get(elem).get('title', ''),
                         'logo': contents.get(elem).get('images', {}).get('thumbnail')[0],
                         'url': contents.get(elem)['video_resources'][0]['manifest']['url'],
                         'needs_login': contents.get(elem).get('needs_login')
                         }
                         for elem in contents]
                
        for item in channel_list:
            id = item.get('channel-id')
            g_list = [key for key, values in groups.items() if id in values]
            item.update({'group': g_list})    

        # print(json.dumps(channel_list, indent=2)) 
        print(f'[INFO] Number of streams available: {len(channel_list)}')
        print(f'[INFO] Valid Duration: {resp.get("valid_duration")}')

        epg_data, error = self.read_epg(channel_id_list)
        if  error: print(error)

        # Create a lookup dictionary for channel_list
        channel_dict = {station.get('channel-id'): station for station in channel_list}

        for listing in epg_data:
            cid = str(listing.get('content_id'))
            tmsid = listing.get('gracenote_id')
    
            if tmsid and cid in channel_dict:
                channel_dict[cid].update({'tmsid': tmsid}) # Updates channel_list in place

        
        self.update_tmsid(channel_dict)




        # print(json.dumps(channel_list, indent=2)) 
        with self.lock:
            self.sessionAt = sessionAt
            self.session_expires_in = int(resp.get("valid_duration"))
            self.channel_list = channel_list
            self.epg_data = epg_data


        return channel_list, None
    
    def epg(self):
        local_sessionAt = self.sessionAt
        local_session_expires_in = self.session_expires_in

        if not self.isTimeExpired(local_sessionAt, local_session_expires_in):
            print("[INFO] Return Cached EPG")
            return None

        print("[INFO] EPG: Updating Channel Data")
        channel_cache, error = self.channels()
        if error: return error

        error = self.save_xml()
        if error: print(f"[ERROR] Saving XML error: {error}")
        return error


    def save_xml(self):
        xml_file_path        = f"epg.xml"
        compressed_file_path = f"{xml_file_path}.gz"

        local_epg_data = self.epg_data.copy()
        # Set your desired timezone, for example, 'UTC'
        desired_timezone = pytz.timezone('UTC')

        if self.user:
            g_name = self.user
        else:
            g_name = ''
        root = ET.Element("tv", attrib={"generator-info-name": g_name, "generated-ts": ""})

        stations = sorted(local_epg_data, key = lambda i: i.get('title', ''))

        for station in stations:
            channel = ET.SubElement(root, "channel", attrib={"id": str(station["content_id"])})
            display_name = ET.SubElement(channel, "display-name")
            display_name.text = station["title"]
            icon = ET.SubElement(channel, "icon", attrib={"src": station["images"]['thumbnail'][0]})

        for station in stations:
            channel_id = str(station["content_id"])
            program_data = station['programs']
            for program in program_data:
                root = self.create_programme_element(program, channel_id, root)

        # Sort the <programme> elements by channel and then by start
        sorted_programmes = sorted(root.findall('.//programme'), key=lambda x: (x.get('channel'), x.get('start')))

        # Clear the existing <programme> elements in the root
        for child in root.findall('.//programme'):
            root.remove(child)

        # Append the sorted <programme> elements to the root
        for element in sorted_programmes:
            root.append(element)

        # Create an ElementTree object
        tree = ET.ElementTree(root)
        ET.indent(tree, '  ')

        # Create a DOCTYPE declaration
        doctype = '<!DOCTYPE tv SYSTEM "xmltv.dtd">'

        # Concatenate the XML and DOCTYPE declarations in the desired order
        xml_declaration = '<?xml version=\'1.0\' encoding=\'utf-8\'?>'

        output_content = xml_declaration + '\n' + doctype + '\n' + ET.tostring(root, encoding='utf-8').decode('utf-8')

        print("[INFO] Writing XML")

        # Write the concatenated content to the output file
        try:
            with open(xml_file_path, "w", encoding='utf-8') as f:
                f.write(output_content)
        except:
            return "[ERROR] Error writing XML"

        with open(xml_file_path, 'r') as file:
            xml_data = file.read()

        # Compress the XML file
        with open(xml_file_path, 'rb') as file:
            with gzip.open(compressed_file_path, 'wb') as compressed_file:
                compressed_file.writelines(file)

        # print("[INFO] End EPG")
        return None


    def create_programme_element(self, program_data, channel_id, root):
        programme = ET.SubElement(root, "programme", attrib={"channel": channel_id,
                                                             "start": datetime.fromisoformat(program_data["start_time"].replace('Z', '+00:00')).strftime("%Y%m%d%H%M%S %z"),
                                                             "stop": datetime.fromisoformat(program_data["end_time"].replace('Z', '+00:00')).strftime("%Y%m%d%H%M%S %z")})

        if program_data.get('title'):
            title = ET.SubElement(programme, "title")
            title.text = program_data.get('title','')

        if program_data.get('episode_title'):
            sub_title = ET.SubElement(programme, "sub-title")
            sub_title.text = program_data.get('episode_title','')

        if program_data.get('season_number') and program_data.get('season_number') != '':
            episode_num_onscreen = ET.SubElement(programme, "episode-num", attrib={"system": "onscreen"})
            if program_data.get('episode_number'):
                episode_num_onscreen.text = f"S{program_data.get('season_number', 0):02d}E{program_data.get('episode_number', 0):02d}"
            else:
                episode_num_onscreen.text = f"Season {program_data.get('season_number', 0)}"

        if program_data.get("description", "") != '':
            desc = ET.SubElement(programme, "desc")
            desc.text = program_data.get('description','')

        image_list = []
        image_list.extend(program_data['images'].get('landscape', []))
        image_list.extend(program_data['images'].get('poster', []))
        image_list.extend(program_data['images'].get('hero', []))

        art = next((item for item in image_list), '')
        if art != '':    
            icon_programme = ET.SubElement(programme, "icon", attrib={"src": art})

        return root

    def read_epg(self, channel_id_list):
        print("[INFO] Retriving EPG API Data")
        epg_data = []

        local_headers = self.headers
        local_device_id = self.device_id
        bearer, error = self.token()
        if error: return None, error
        local_headers.update({'authorization': f'Bearer {bearer}',
                              'x-tubi-mode': 'all',
                              'x-tubi-platform': 'web'
                              })

        params = {'platform': 'web',
                  'device_id': local_device_id,
                  'lookahead': 1,
                 }

        url = 'https://epg-cdn.production-public.tubi.io/content/epg/programming'

        # print(json.dumps(local_headers, indent =2))
        # sessionAt = time.time()
        group_size = 150
        grouped_id_values = [channel_id_list[i:i + group_size] for i in range(0, len(channel_id_list), group_size)]

        for group in grouped_id_values:
            session = requests.Session()
            params.update({"content_id": ','.join(map(str, group))})


            try:
                session = requests.Session()
                programmingResponse = session.get(url, params=params, headers=local_headers)
            except requests.ConnectionError as e:
                error = f"Connection Error. {str(e)}"
            finally:
                print('[INFO] Close the Programming API session')
                session.close()

            if error:
                print (f'[ERROR] {error}')
                return None, error

            if programmingResponse.status_code != 200:
                print(f"[ERROR] HTTP: {programmingResponse.status_code}: {programmingResponse.text}")
                return None, programmingResponse.text
            resp = programmingResponse.json()

            epg_data.extend(resp.get('rows',[]))
        print(f'[INFO] Programming data size: {len(epg_data)}')
        return epg_data, None

    def generate_playlist(self, provider, args, host):
        error = None
        gracenote = args.get('gracenote')
        filter_stations = args.get('filtered')

        stations, error = self.channels()
        if error: return None, error

        # Filter out Hidden items or items without Hidden Attribute
        tmsid_stations = list(filter(lambda d: d.get('tmsid'), stations))
        no_tmsid_stations = list(filter(lambda d: d.get('tmsid', "") == "" or d.get('tmsid') is None, stations))

        if 'unfiltered' not in args and gracenote == 'include':
            data_group = tmsid_stations
        elif  'unfiltered' not in args and gracenote == 'exclude':
            data_group = no_tmsid_stations
        else:
            data_group = stations

        data_group = sorted(data_group, key = lambda i: i.get('name', ''))

        m3u = "#EXTM3U\r\n\r\n"
        for s in data_group:
            if s.get('needs_login'):
                print(f'[INFO] Skipping {s.get("name")}: Requires Login')
            else:
                m3u += f"#EXTINF:-1 channel-id=\"{provider}-{s.get('channel-id')}\""
                m3u += f" tvg-id=\"{s.get('channel-id')}\""
                m3u += f" tvg-chno=\"{''.join(map(str, s.get('number', [])))}\"" if s.get('number') else ""
                m3u += f" group-title=\"{';'.join(map(str, s.get('group', [])))}\"" if s.get('group') else ""
                m3u += f" tvg-logo=\"{''.join(map(str, s.get('logo', [])))}\"" if s.get('logo') else ""
                m3u += f" tvg-name=\"{s.get('call_sign')}\"" if s.get('call_sign') else ""
                if gracenote == 'include':
                    m3u += f" tvg-shift=\"{s.get('time_shift')}\"" if s.get('time_shift') else ""
                    m3u += f" tvc-guide-stationid=\"{s.get('tmsid')}\"" if s.get('tmsid') else ""
                m3u += f",{s.get('name') or s.get('call_sign')}\n"
                # m3u += f"{s.get('url')}\n\n"
                m3u += f"http://{host}/{provider}/watch/{s.get('channel-id')}\n\n"

        return m3u, error

    def generate_video_url(self, id):
        channel_list, error = self.channels()
        if error: return None, error

        # Create a lookup dictionary for channel_list
        channel_dict = {station.get('channel-id'): station for station in channel_list}

        url = channel_dict.get(id, {}).get('url')
        # print(f'[INFO] {url}')
        return url, None
