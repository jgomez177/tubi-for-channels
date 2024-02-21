# Tubi for Channels

Current version: **0.90**

# About
This takes Tubi Live TV Channels and generates an M3U playlist and EPG XMLTV file.

# Running
The recommended way of running is to pull the image from [GitHub](https://github.com/jgomez177/tubi-for-channels/pkgs/container/tubi-for-channels).

    docker run -d --restart unless-stopped --network=host -e TUBI_PORT=[your_port_number_here] --name  tubi-for-channels ghcr.io/jgomez177/tubi-for-channels
or

    docker run -d --restart unless-stopped -p [your_port_number_here]:7777 --name  tubi-for-channels ghcr.io/jgomez177/tubi-for-channels

You can retrieve the playlist and EPG via the status page.

    http://127.0.0.1:[your_port_number_here]

## Environement Variables
| Environment Variable | Description | Default |
|---|---|---|
| TUBI_PORT | Port the API will be served on. You can set this if it conflicts with another service in your environment. | 7777 |

## Additional URL Parameters
| Parameter | Description |
|---|---|
| gracenote | "include" will utilize gracenote EPG information and filter to those streams utilizing Gracenote. "exclude" will filter those streams that do not have a matching gracenote EPG data. |

## Optional Custom Gracenote ID Matching

Adding a docker volume to /app/tubi_data will allow you to add a custom comma delimited csv file to add or change any of the default gracenote matching for any tubi channel

    docker run -d --restart unless-stopped --network=host -e TUBI_PORT=[your_port_number_here] -v [your_file_location_here]:/app/tubi_data --name  tubi-for-channels ghcr.io/jgomez177/tubi-for-channels

Create a file called `tubi_custom_tmsid.csv` with the following headers (case-sensitive):
| id |  name | tmsid | time_shift | 
|---|---|---|---|
| (required) id of the Tubi channel (more on obtaining this ID below) | (optional) Easy to read name | (required) New/Updated Gracenote TMSID number for the channel | (optional) Shifting EPG data for the channel in hours. Ex: To shift the EPG 5 hours earlier, value would be -5 | 

Example

    id,name,tmsid,time_shift
    400000011,TV One Crime & Justice,145680,

