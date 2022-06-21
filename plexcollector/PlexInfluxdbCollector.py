import base64
import dataclasses
import json
import sys
import time
from typing import List, Dict
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import plexapi.base
import plexapi.library
import requests
import urllib3.exceptions
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from plexapi.server import PlexServer
from requests import ConnectTimeout

from plexcollector.common import log
from plexcollector.common.sctructures import StreamData, MEDIA_TYPES, \
    MEDIA_TYPE
from plexcollector.config import config


# TODO - Update readme for PMS SSL
class PlexInfluxdbCollector:
    def __init__(self, single_run=False):
        self.server_addresses = config.plex_server_addresses
        self.plex_servers: List[PlexServer] = []
        self.logger = log
        self.token = None
        self.single_run = single_run
        self.active_streams = {}  # Store active streams so we can track duration
        self.delay = config.delay
        self.influx_client = self._get_influx_connection()

        # Prevents console spam if verify ssl is disabled
        if not config.plex_verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self._build_server_list()

    def _build_server_list(self):
        """
        Build a list of plexapi objects from the servers provided in the config
        :return:
        """
        for server in self.server_addresses:
            base_url = config.url(server)
            session = requests.Session()
            session.verify = config.plex_verify_ssl
            api_conn = PlexServer(
                base_url,
                self.get_auth_token(
                    config.plex_user, config.plex_password
                ),
                # session=session
            )
            self.plex_servers.append(api_conn)

    @staticmethod
    def _get_influx_connection():
        """
        Create an InfluxDB connection and test to make sure it works.
        We test with the get all users command.  If the address is bad it fails
        with a 404.  If the user doesn't have permission it fails with 401
        :return:
        """
        # TODO - Check what permissions are actually needed to make this work
        influx = InfluxDBClient(
            host=config.influx_address,
            port=config.influx_port,
            database=config.influx_database,
            ssl=config.influx_ssl,
            verify_ssl=config.influx_verify_ssl,
            username=config.influx_user,
            password=config.influx_password,
            timeout=5
        )
        try:
            log.debug('Testing connection to InfluxDb using provided credentials')
            influx.get_list_users()  # TODO - Find better way to test connection and permissions
            log.debug('Successful connection to InfluxDb')
        except (ConnectTimeout, InfluxDBClientError) as e:
            if isinstance(e, ConnectTimeout):
                log.critical('Unable to connect to InfluxDB at the provided address (%s)', config.influx_address)
            elif e.code == 401:
                log.critical('Unable to connect to InfluxDB with provided credentials')

            sys.exit(1)

        return influx

    def get_auth_token(self, username, password):
        """
        Make a reqest to plex.tv to get an authentication token for future requests
        :param username: Plex Username
        :param password: Plex Password
        :return: str
        """

        log.info('Getting Auth Token For User {}'.format(username))

        auth_string = '{}:{}'.format(username, password)
        base_auth = base64.encodebytes(bytes(auth_string, 'utf-8'))
        req = self.request('https://plex.tv/users/sign_in.json')
        req.add_header('Authorization', f'Basic {base_auth[:-1].decode("utf-8")}')

        try:
            result = urlopen(req, data=b'').read()
        except HTTPError as e:
            print('Failed To Get Authentication Token')
            if e.code == 401:
                log.error('Failed to get token due to bad username/password')
            else:
                print('Maybe this will help:')
                print(e)
                log.error('Failed to get authentication token.  No idea why')
            sys.exit(1)

        output = json.loads(result.decode('utf-8'))

        # Make sure we actually got a token back
        if 'authToken' in output['user']:
            log.debug('Successfully Retrieved Auth Token')
            return output['user']['authToken']
        else:
            print('Something Broke \n We got a valid response but for some reason there\'s no auth token')
            sys.exit(1)

    def request(self, url: str) -> Request:
        """
        Make a request to plex.tv
        """
        return Request(url, headers=self._default_headers)

    @property
    def _default_headers(self):
        headers = {
            'X-Plex-Client-Identifier': 'Plex InfluxDB Collector',
            'X-Plex-Product': 'Plex InfluxDB Collector',
            'X-Plex-Version': '1',
        }
        if self.token:
            headers['X-Plex-Token'] = self.token
        return headers

    def get_active_streams(self):
        log.info('Attempting to get active sessions')

        active_streams = {
            server._baseurl: server.sessions()
            for server in self.plex_servers
        }

        self._process_active_streams(active_streams)

    def _process_active_streams(self, stream_data: Dict[str, List[MEDIA_TYPE]]):
        """
        Take an object of stream data and create Influx JSON data
        :param stream_data:
        :return:
        """

        log.info('Processing Active Streams')

        combined_streams = 0
        session_ids = []  # Active Session IDs for this run

        for host, streams in stream_data.items():

            combined_streams += len(streams)
            combined_video_transcodes = 0
            combined_audio_transcodes = 0

            for stream in streams:
                player = stream.players[0]
                user = stream.usernames[0]
                session_id = stream.session[0].id
                session_ids.append(session_id)

                if session_id in self.active_streams:
                    start_time = self.active_streams[session_id]['start_time']
                else:
                    start_time = time.time()
                    self.active_streams.setdefault(session_id, {})['start_time'] = start_time

                media_type = MEDIA_TYPES.get(stream.type, 'Unknown')
                print(media_type)

                data, video, audio = StreamData().stream_processor(stream)

                # playing, paused, buffering
                player_state = getattr(player, 'state', 'Unavailable')

                combined_video_transcodes += video
                combined_audio_transcodes += audio

                log.debug(f'Title: {data.full_title}')
                log.debug(f'Media Type: {media_type}')
                log.debug(f'Session ID: {session_id}')
                log.debug(f'Resolution: {data.resolution}')
                log.debug(f'Duration: {time.time() - start_time}')
                log.debug(f'Transcode Video: {data.transcode_video}')
                log.debug(f'Transcode Audio: {data.transcode_audio}')
                log.debug(f'Container: {data.container}')
                log.debug(f'Video Codec: {data.video_codec}')
                log.debug(f'Audio Codec: {data.audio_codec}')
                log.debug(f'Length ms: {data.length_ms}')
                log.debug(f'Position: {data.position}')
                log.debug(f'Pos Percent: {data.pos_percent}')

                playing_points = [
                    {
                        'measurement': 'now_playing',
                        'fields': {
                            'player': player.title,
                            'state': player.state,
                            'user': user,
                            'media_type': media_type,
                            'duration': time.time() - start_time,
                            'start_time': start_time,
                            'platform': player.platform,
                            'player_state': player_state,
                            **dataclasses.asdict(data)
                        },
                        'tags': {
                            'host': host,
                            'player_address': player.address,
                            'session_id': session_id
                        }
                    }
                ]

                self.write_influx_data(playing_points)

            # Record total streams for this host
            total_stream_points = [
                {
                    'measurement': 'active_streams',
                    'fields': {
                        'active_streams': len(streams),
                        'video_transcodes': combined_video_transcodes,
                        'audio_transcodes': combined_audio_transcodes
                    },
                    'tags': {
                        'host': host
                    }
                }
            ]
            self.write_influx_data(total_stream_points)

        # Report total streams across all hosts
        if config.report_combined:
            combined_stream_points = [
                {
                    'measurement': 'active_streams',
                    'fields': {
                        'active_streams': combined_streams
                    },
                    'tags': {
                        'host': 'All'
                    }
                }
            ]

            self.write_influx_data(combined_stream_points)
            self._remove_dead_streams(session_ids)

    def _remove_dead_streams(self, current_streams):
        """
        Go through the stored list of active streams and remove any that are no longer active
        :param current_streams: List of currently active streams from last API call
        :return:
        """
        remove_keys = []
        for id, data in self.active_streams.items():
            if id not in current_streams:
                remove_keys.append(id)
        for key in remove_keys:
            self.active_streams.pop(key)

    def get_library_data(self):
        """
        Get all library data for each provided server.
        """
        # TODO This might take ages in large libraries.  Add a separate delay for this check
        lib_data = {}

        for server in self.plex_servers:
            libs: List[plexapi.library.LibrarySection] = server.library.sections()
            log.info('We found {} libraries for server {}'.format(str(len(libs)), server))
            host_libs = []
            for lib in libs:
                host_lib = {
                    'tags': {
                        'lib_name': lib.title,
                        'lib_type': lib.type,
                    },
                    'items': len(lib.search())
                }

                if lib.type == "show":
                    host_lib['episodes'] = 0
                    host_lib['seasons'] = 0
                    shows = lib.search()
                    for show in shows:
                        log.debug('Checking TV Show: %s', show.title)
                        host_lib['episodes'] += len(show.seasons())
                        host_lib['seasons'] += len(show.episodes())

                host_libs.append(host_lib)
            lib_data[server] = host_libs

        self._process_library_data(lib_data)

    def get_recently_added(self):
        """
        Build list of recently added
        :return:
        """

        for server in self.plex_servers:
            recent_list = []

            for section in server.library.sections():
                recent_list += section.recentlyAdded(maxresults=10)

            for item in recent_list:
                data = {
                    'measurement': 'recently_added',
                    'fields': {
                        'media_type': item.type.title(),
                        'added_at': item.addedAt.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    },
                    'tags': {
                        'host': server._baseurl
                    }
                }

                if hasattr(item, 'grandparentTitle'):
                    data['fields']['title'] = item.grandparentTitle + ' - ' + item.title
                else:
                    data['fields']['title'] = item.title

                self.write_influx_data([data])

    def _process_library_data(self, lib_data):
        """
        Breakdown the provided library data and format for InfluxDB
        """
        print(lib_data)
        log.info('Processing Library Data')

        for host, data in lib_data.items():
            for lib in data:
                fields = {
                    'items': lib['items'],
                }
                for key in ['episodes', 'seasons']:
                    if key in lib:
                        fields[key] = lib[key]
                lib_points = [
                    {
                        'measurement': 'libraries',
                        'fields': fields,
                        'tags': {
                            'host': host,
                            **lib['tags'],
                        }
                    }
                ]
                self.write_influx_data(lib_points)

    def write_influx_data(self, json_data):
        """
        Writes the provided JSON to the database
        :param json_data:
        :return:
        """
        log.debug(json_data)

        try:
            self.influx_client.write_points(json_data)
        except (InfluxDBClientError, ConnectionError, InfluxDBServerError) as e:
            if hasattr(e, 'code') and e.code == 404:
                log.error('Database {} Does Not Exist.  Attempting To Create')
                self.influx_client.create_database(config.influx_database)
                self.influx_client.write_points(json_data)
                return
            log.error('Failed to write data to InfluxDB')

        log.debug('Written To Influx: {}'.format(json_data))

    def run(self):

        log.info('Starting Monitoring Loop')
        while True:
            self.get_recently_added()
            self.get_library_data()
            self.get_active_streams()
            if self.single_run:
                return
            time.sleep(self.delay)
