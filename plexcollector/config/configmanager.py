import configparser
import os
import sys
from typing import Tuple, Iterable

import requests


class ConfigManager:

    def __init__(self, config):

        print('Loading config: ' + config)

        config_file = os.path.join(os.getcwd(), config)
        if os.path.isfile(config_file):
            self.config = configparser.ConfigParser()
            self.config.read(config_file)
        else:
            print('ERROR: Unable To Load Config File: {}'.format(config_file))
            sys.exit(1)

        self._load_config_values()
        self._validate_plex_servers()
        print('Configuration Successfully Loaded')

    def _load_config_values(self):

        # General
        general = self.config['GENERAL']
        self.delay = general.getint('Delay', fallback=2)
        self.report_combined = general.getboolean('ReportCombined', fallback=True)

        # InfluxDB
        influx = self.config['INFLUXDB']
        self.influx_address = influx['Address']
        self.influx_port = influx.getint('Port', fallback=8086)
        self.influx_database = influx.get('Database', fallback='plex_data')
        self.influx_ssl = influx.getboolean('SSL', fallback=False)
        self.influx_verify_ssl = influx.getboolean('Verify_SSL', fallback=True)
        self.influx_user = influx.get('Username', fallback='')
        self.influx_password = influx.get('Password', fallback='', raw=True)

        # Plex
        plex = self.config['PLEX']
        self.plex_user = plex['Username']
        self.plex_password = plex.get('Password', raw=True)
        plex_https = plex.getboolean('HTTPS', fallback=False)
        self.conn_security = 'https' if plex_https else 'http'
        self.port = plex.getint('Port', fallback=32469 if plex_https else 32400)
        self.plex_verify_ssl = plex.getboolean('Verify_SSL', fallback=False)
        servers = len(plex['Servers'])

        # Logging
        self.logging_level = self.config['LOGGING']['Level'].upper()

        if servers:
            self.plex_server_addresses = plex['Servers'].replace(' ', '').split(',')
        else:
            print('ERROR: No Plex Servers Provided.\nAborting!')
            sys.exit(1)

    def url(self, server):
        return '{}://{}:{}'.format(self.conn_security, server, self.port)

    @property
    def urls(self):
        return map(self.url, self.plex_server_addresses)

    @property
    def servers_url(self) -> Iterable[Tuple[str, str]]:
        return map(lambda x: (x, self.url(x)), self.plex_server_addresses)

    def _validate_plex_servers(self):
        """
        Make sure the servers provided in the config can be resolved.  Abort if they can't
        :return:
        """
        failed_servers = []
        for server, server_url in self.servers_url:
            try:
                r = requests.get(server_url, verify=self.plex_verify_ssl)
                if r.status_code == 401:
                    continue
                print('Unexpected status code {} from Plex server'.format(str(r.status_code)))
            except ConnectionError:
                print('Failed to connect to Plex server', server)
                failed_servers.append(server)

        # Do we have any valid servers left?
        # TODO This check is failing even with no bad servers
        if len(self.plex_server_addresses) > len(failed_servers):
            print('INFO: Found {} Bad Server(s).  Removing Them From List'.format(str(len(failed_servers))))
            for server in failed_servers:
                self.plex_server_addresses.remove(server)
        else:
            print('ERROR: No Valid Servers Provided.  Check Server Addresses And Try Again')
            sys.exit(1)
