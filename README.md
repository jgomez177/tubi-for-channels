# Tubi for Channels

Current version: **3.00**

# About
This takes Tubi Live TV Channels and generates an M3U playlist and EPG XMLTV file.

# Changes
 - Version 3.00: 
    - Total rebuild of container.
    - New API calling
    - Improved error handling
    - Improved threading
 - Version 2.06: 
    - More Internal Updates
 - Version 2.05: 
    - Added Group Listings
 - Version 2.04: 
    - Corrected timing for EPG updates
 - Version 2.03: 
    - Corrected Bad Function Call
 - Version 2.02: 
    - Adding multithreading
 - Version 2.01: 
    - Additional improvements and logging
 - Version 2.00: 
    - Included support for email signin (not Google authentication)
    - Additional Updates
 - Version 1.03a: 
    - More error handling
 - Version 1.03: 
    - Added additional error handling
 - Version 1.02: 
    - Updated TMSID handing to clear incorrect Tubi listed TMSIDs
 - Version 1.01: 
    - Added Error handling for when channel does not have URL Stream
 - Version 1.00: 
    - Main Release
    - Added EPG Scheduler.
    - Updates to Gracenote Mapping


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
| TUBI_USER | Optional variable to sign into Tubi Account. | None |
| TUBI_PASS | Optional variable to sign into Tubi Account. | None |

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


***

If you like this and other linear containers for Channels that I have created, please consider supporting my work.

[![](https://pics.paypal.com/00/s/MDY0MzZhODAtNGI0MC00ZmU5LWI3ODYtZTY5YTcxOTNlMjRm/file.PNG)](https://www.paypal.com/donate/?hosted_button_id=BBUTPEU8DUZ6J)