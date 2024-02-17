import secrets, requests, json, re, time, pytz, gzip, csv, os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from urllib.parse import unquote

class Client:
    def __init__(self):
        self.session = requests.Session()
        self.load_device()
        self.channel_list = []
        self.country_stations = {}
        self.sessionAt = 0
        self.epg_data = []

        self.headers = {
                    # 'authority': 'clients.plex.tv',
                    # 'accept': 'application/json, text/javascript, */*; q=0.01',
                    # 'accept-language': 'en',
                    # 'content-length': '0',
                    # 'origin': 'https://app.plex.tv',
                    # 'referer': 'https://app.plex.tv/',
                }

        self.params = {
                    # 'X-Plex-Product': 'Plex Web',
                    # 'X-Plex-Version': '4.120.1',
                    # 'X-Plex-Client-Identifier': self.device,
                    # 'X-Plex-Language': 'en',
                }

    def load_device(self):
        try:
            with open("tubi-device.json", "r") as f:
                self.device = json.load(f)
        except FileNotFoundError:
            self.device = secrets.token_hex(12)
            with open("tubi-device.json", "w") as f:
                json.dump(self.device, f)

    def replace_quotes(self, match):
        return '"' + match.group(1).replace('"', r'\"') + '"'

    def channel_id_list(self):
        url = "https://tubitv.com/live"
        params = {}
        headers = {}

        try:
            response = requests.get(url, params=params, headers=headers)
        except Exception as e:
            return (f"read_from_tubi Exception type Error: {type(e).__name__}")    

        if (response.status_code != 200):
            return (f"tubitv.com/live HTTP failure {response.status_code}: {response.text}")
        
        html_content  = response.text

        # Parse the HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all <script> tags
        script_tags = soup.find_all("script")

        # Look for the script starting with "window.__data"
        target_script = None
        for script in script_tags:
            if script.string and script.string.strip().startswith("window.__data"):
                target_script = script.string
                break

        if target_script is None:
            return f"Error: No Data located"
        
        # Extract JSON part from the string
        # Find the start and end positions of the JSON part
        start_index = target_script.find("{")
        end_index = target_script.rfind("}") + 1

        # Extract the JSON part
        json_string = target_script[start_index:end_index]

        # Replace 'undefined' with 'null' to make it valid JSON
        json_string = re.sub(r'\bundefined\b', 'null', json_string)

        # More corrections for valid JSON
        pattern = r'(new\s+Date\("[^"]*"\)|read\s+Date\("[^"]*"\))'
        data = re.sub(pattern, self.replace_quotes, json_string)
        # print(new_text)

        try:
            data_json = json.loads(data)
        except Exception as e:
            return f"read_from_tubi json Exception type Error: {type(e).__name__}"

        epg = data_json.get('epg')
        contentIdsByContainer = epg.get('contentIdsByContainer')
        skip_slugs = ['favorite_linear_channels', 'recommended_linear_channels', 'featured_channels', 'recently_added_channels']
        self.channel_list = [content for key in contentIdsByContainer.keys() for item in contentIdsByContainer[key] if item['container_slug'] not in skip_slugs for content in item["contents"]]
        print(f'[INFO] Number of streams available: {len(self.channel_list)}')
        # print(all_contents)
        self.sessionAt = time.time()
        return None

    def read_epg(self):
        if (time.time() - self.sessionAt) < 4 * 60 * 60:
            # print("[INFO] Time Check")
            if len(self.epg_data) > 0:
                print("[INFO] Returning cached EPG Data")
                return None
        
        print("[INFO] Retriving EPG Data")

        epg_headers =   {}

        # # Get the current time in the desired timezone
        # start_datetime = datetime.now(desired_timezone)
        # # start_time = quote(start_datetime.strftime("%Y-%m-%d %H:00:00.000Z"))
        # start_time = start_datetime.strftime("%Y-%m-%d")

        if len(self.channel_list ) == 0:
            print("[INFO] Initialize channel_list")
            error = self.channel_id_list()
            if error: return error

        epg_data = []

        group_size = 150
        grouped_id_values = [self.channel_list[i:i + group_size] for i in range(0, len(self.channel_list), group_size)]
        root = ET.Element("tv", attrib={"generator-info-name": "jgomez177", "generated-ts": ""})

        for group in grouped_id_values:
            session = requests.Session()
            params = {"content_id": ','.join(map(str, group))}

            response = session.get(f'https://tubitv.com/oz/epg/programming', params=params)
            if (response.status_code != 200):
                return None, f"tubitv.com/oz/epg HTTP failure for {group} {response.status_code}: {response.text}"

            js = response.json()
            epg_data.extend(js.get('rows',[]))
        
        self.epg_data = epg_data

        return None

    def channels(self):
        if (time.time() - self.sessionAt) > 4 * 60 * 60:
            print("[INFO] Reading channel id list cache")
            error = self.read_epg()
            if error: return None, error
        else:
            print("[INFO] Updating channel id list")
            error = self.channel_id_list()
            if error: return None, error
            error = self.read_epg()
            if error: return None, error
        print(f"[INFO] Channels: Available EPG data: {len(self.epg_data)}")
        channels = [{'channel-id': str(elem.get('content_id')),
                     'name': elem.get('title', ''),
                     'logo': elem['images'].get('thumbnail'),
                     'url': f"{unquote(elem['video_resources'][0]['manifest']['url'])}&content_id={elem.get('content_id')}",
                     'tmsid': elem.get('gracenote_id', None)}
                     for elem in self.epg_data]

        
        tubi_custom_tmsid = 'tubi_data/tubi_custom_tmsid.csv'
        tmsid_dict = {}
        if os.path.exists(tubi_custom_tmsid):
            # File exists, open it
            with open(tubi_custom_tmsid, mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    tmsid_dict[row['id']] = row

        channels = [{**entry, 'tmsid': tmsid_dict[entry["channel-id"]]['tmsid'], 'time_shift': tmsid_dict[entry["channel-id"]]['time_shift']}
                    if entry["channel-id"] in tmsid_dict and tmsid_dict[entry["channel-id"]]['time_shift'] != ''
                    else {**entry, 'tmsid': tmsid_dict[entry["channel-id"]]['tmsid']} if entry["channel-id"] in tmsid_dict and tmsid_dict[entry["channel-id"]]['tmsid'] != ''
                    else entry
                    for entry in channels]
        
        channels = sorted(channels, key=lambda x: x['name'].lower())
        print(f"[INFO] Channels: Number of streams available: {len(channels)}")
        return channels, None

    def clear_data(self):
        self.channel_list = []
        self.sessionAt = 0
        self.epg_data = []
        return

    def epg_json(self):
        error = self.read_epg()
        if error: return error
        return sorted(self.epg_data, key = lambda i: i.get('title', '')), error
    

    def epg(self):
        if (time.time() - self.sessionAt) < 4 * 60 * 60:
            print("[INFO] Returning cached EPG File")
            return None

        error = self.read_epg()
        if error: return error

        xml_file_path        = f"epg.xml"
        compressed_file_path = f"{xml_file_path}.gz"

        # Set your desired timezone, for example, 'UTC'
        desired_timezone = pytz.timezone('UTC')


        root = ET.Element("tv", attrib={"generator-info-name": "jgomez177", "generated-ts": ""})

        stations = sorted(self.epg_data, key = lambda i: i.get('title', ''))


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

        

        # root = self.read_epg_data(root)

        # Sort the <programme> elements by channel and then by start
        sorted_programmes = sorted(root.findall('.//programme'), key=lambda x: (x.get('channel'), x.get('start')))

        # Clear the existing elements in the root
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

        # Write the concatenated content to the output file
        try:
            with open(xml_file_path, "w", encoding='utf-8') as f:
                f.write(output_content)
        except:
            return "Error"


        with open(xml_file_path, 'r') as file:
            xml_data = file.read()

        # Compress the XML file
        with open(xml_file_path, 'rb') as file:
            with gzip.open(compressed_file_path, 'wb') as compressed_file:
                compressed_file.writelines(file)

        return None

    def create_programme_element(self, program_data, channel_id, root):
        # print(f"Channel id is {channel_id}")
        # print(json.dumps(program_data, indent = 2))

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
