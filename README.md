**Plex to InfluxDB Extended**
------------------------------
This project forked from the original, awesome [Plex-Data-Collector-For-InfluxDB by barrycarey](https://github.com/barrycarey/Plex-Data-Collector-For-InfluxDB).

![Screenshot](https://puu.sh/tarSA/aea875c453.png)

This is a tool for collecting info from your Plex server and sending it to InfluxDB.  This is ideal for displaying Plex specific information in a tool such as Grafana.

## Configuration within config.ini

#### GENERAL
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Delay          |Delay between updating metrics                                                                                      |
|Output         |Write console output while tool is running                                                                          |
#### INFLUXDB
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Address        |IP address or FQDN of influxdb server                                                                               |
|Port           |InfluxDB port to connect to.  8086 in most cases                                                                    |
|Database       |Database to write collected stats to                                                                                |
|Username       |User that has access to the database                                                                                |
|Password       |Password for above user                                                                                             |
#### PLEX
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Username       |Plex username                                                                                                       |
|Password       |Plex Password                                                                                                       |
|Servers        |A comma separated list of servers you wish to pull data from.                                                       |
#### LOGGING
|Key            |Description                                                                                                         |
|:--------------|:-------------------------------------------------------------------------------------------------------------------|
|Enable         |Output logging messages to provided log file                                                                        |
|Level          |Minimum type of message to log.  Valid options are: critical, error, warning, info, debug                           |
|LogFile        |File to log messages to.  Can be relative or absolute path                                                          |
|CensorLogs     |Censor certain things like server names and IP addresses from logs                                                  |


### Usage

Enter your desired information in config.ini and run plexInfluxdbCollector.py

Optionally, you can specify the --config argument to load the config file from a different location.  


#### Requirements

*Python 3+*

You will need the [*influxdb library*](https://github.com/influxdata/influxdb-python) installed to use this.  Typically this can be installed from the command line using:

```
pip3 install influxdb
```

## InfluxDB Fields
|Field              |Description                                                                                            |
|:------------------|:------------------------------------------------------------------------------------------------------|
|media_type         | Movie, TV Show, Music, or Unknown                                                                     |
|stream_title       | For TV and Music: An aggregation of the grandparent title (series or artist name) and track or episode title. For movies, the movie title|
|grandparent_title  | Blank for movies. Series title for TV shows. Artist title for music                                   |
|parent_title       | Blank for movies. Season title (e.g. Season 1) for TV Shows. Album title for music                    |
|parent_index       | Blank for movies and music. Season number for TV shows                                                |
|title              | Movie, episode, or track title                                                                        |
|year               | Blank for music. Series or Movie year of release                                                      |
|index              | Blank for movies. Episode number for TV Shows. Track number for music.                                |
|container          | File type of the media (e.g. mkv, mp4, mp3, flac, etc.)                                                |
|resolution         | Video resolution (e.g. 4k, 1080p, 720p) for movies and TV. Audio bitrate for music.                   |
|video_codec        | Codec for video stream (e.g. h264, h265, mpeg)                                                        |
|audio_codec        | Codec for audio stream                                                                                |
|transcode_video    | DirectPlay, DirectStream (container remux usually because audio is being transcoded or client doesn't natively support container), or Transcoding|
|transcode_audio    | DirectPlay, DirectStream, or Transcode                                                                        |
|transcode_summary  | Reflects transcoding status of both video and audio (or just audio in the case of music)              |
|video_framerate    | Frame rate for video stream. Blank for music                                                          |
|length_ms          | Length of track, epsidode, or movie in milliseconds                                                   |
|player             | Device name of client playing the media                                                               |
|user               | User name playing the media                                                                           |
|platform           | OS or application playing the media (e.g. Android, Firefox, etc.)                                     |
|start_time         | Time when playback session started OR when first seen by Plex-Data-Collector-Extended (see notes below)|
|duration           | How long the playback session has been active (see notes below)                                       |
|position_ms        | Current playback position in milliseconds                                                             |
|pos_percent        | Current playback position as a percent of length.  Value is between 0 and 1.                          |
|status             | Current session status (playing, paused, buffering)                                                   |


#### Notes:
The start_time and duration fields are manually calculated by the application based on when it first receives data about a session.  It is accurate to within the value used for ***delay*** in the config.ini file.
Since the Plex API doesn't provide retrospective information for streams that are already in-progress, the duration and start_time will be calculated based on when Plex-Data-Collector-Extend is started.

***Grafana and start_time field***
If you are using Grafana to generate a dashboard, the start_time field will appear to have an incorrect date.  To resolve this, use a math operator to multiply the start_time field by 1000.

## InfluxDB Tags
|Tag                |Description                                                                                            |
|:------------------|:------------------------------------------------------------------------------------------------------|
|host               |Name of Plex server that stream is being played from                                                   |
|player_address     |IP address of client                                                                                   |
|session_id         |Plex internal ID number for playback session                                                           |


