#!/usr/bin/env python3

import logging
import time
import os
import sys
import grpc
import ssl
import requests
from typing import List, Optional

sys.path.insert(0, os.path.dirname(__file__))

from protos.api import backend_pb2
from protos.api import backend_pb2_grpc
from protos.api import frontend_pb2
from protos.api import frontend_pb2_grpc
from protos.api import messages_pb2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
OPEN_MATCH_BACKEND_SERVICE = os.getenv(
    'OPEN_MATCH_BACKEND_SERVICE',
    'open-match-backend.open-match.svc.cluster.local:50505'
)
MATCH_FUNCTION_HOST = os.getenv(
    'MATCH_FUNCTION_HOST',
    'matchfunction.open-match.svc.cluster.local'
)
MATCH_FUNCTION_PORT = os.getenv('MATCH_FUNCTION_PORT', '50502')
AGONES_ALLOCATOR_ENDPOINT = os.getenv(
    'AGONES_ALLOCATOR_ENDPOINT',
    'agones-allocator.agones-system.svc.cluster.local'
)
AGONES_ALLOCATOR_PORT = os.getenv('AGONES_ALLOCATOR_PORT', '443')
AGONES_NAMESPACE = os.getenv('AGONES_NAMESPACE', 'game')
AGONES_FLEET = os.getenv('AGONES_FLEET', 'ue5-gameserver-fleet')

# Agones用のTLS証明書
AGONES_CLIENT_CERT = os.getenv('AGONES_CLIENT_CERT', '/app/certs/client.crt')
AGONES_CLIENT_KEY = os.getenv('AGONES_CLIENT_KEY', '/app/certs/client.key')
AGONES_CA_CERT = os.getenv('AGONES_CA_CERT', '/app/certs/ca.crt')

# マッチングサイクルの間隔（秒）
FETCH_INTERVAL = int(os.getenv('FETCH_INTERVAL', '5'))


class Director:

    def __init__(self):
        self.backend_addr = OPEN_MATCH_BACKEND_SERVICE
        self.match_function_addr = f"{MATCH_FUNCTION_HOST}:{MATCH_FUNCTION_PORT}"
        self.agones_allocator_url = f"https://{AGONES_ALLOCATOR_ENDPOINT}:{AGONES_ALLOCATOR_PORT}/gameserverallocation"

        logger.info(f"Backend: {self.backend_addr}")
        logger.info(f"MatchFunction: {self.match_function_addr}")
        logger.info(f"Agones Allocator: {self.agones_allocator_url}")

    def create_match_profile(self) -> messages_pb2.MatchProfile:
        pool = messages_pb2.Pool(name="everyone")
        profile = messages_pb2.MatchProfile(
            name="simple-2player-profile",
            pools=[pool]
        )
        return profile

    def create_function_config(self) -> backend_pb2.FunctionConfig:
        config = backend_pb2.FunctionConfig(
            host=MATCH_FUNCTION_HOST,
            port=int(MATCH_FUNCTION_PORT),
            type=backend_pb2.FunctionConfig.GRPC
        )
        return config

    def fetch_matches(self, profile: messages_pb2.MatchProfile) -> List[messages_pb2.Match]:
        try:
            logger.info("Fetching matches from OpenMatch Backend...")

            channel = grpc.insecure_channel(self.backend_addr)
            stub = backend_pb2_grpc.BackendServiceStub(channel)

            function_config = self.create_function_config()
            request = backend_pb2.FetchMatchesRequest(
                config=function_config,
                profile=profile
            )

            matches = []
            try:
                response_iterator = stub.FetchMatches(request, timeout=30)

                for response in response_iterator:
                    if response.match and len(response.match.tickets) > 0:
                        matches.append(response.match)
                        logger.info(f"Received match: {response.match.match_id} "
                                  f"with {len(response.match.tickets)} tickets")

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.UNAVAILABLE:
                    logger.warning("OpenMatch Backend unavailable")
                else:
                    logger.error(f"gRPC error fetching matches: {e.code()} - {e.details()}")

            channel.close()

            logger.info(f"Fetched {len(matches)} matches")
            return matches

        except Exception as e:
            logger.error(f"Error fetching matches: {e}", exc_info=True)
            return []

    def allocate_game_server(self) -> Optional[dict]:
        try:
            allocation_request = {
                "apiVersion": "allocation.agones.dev/v1",
                "kind": "GameServerAllocation",
                "spec": {
                    "required": {
                        "matchLabels": {
                            "agones.dev/fleet": AGONES_FLEET
                        }
                    }
                }
            }

            logger.info(f"Allocating GameServer from fleet {AGONES_FLEET}...")

            # TLS証明書の存在確認
            use_tls = all(os.path.exists(f) for f in [AGONES_CLIENT_CERT, AGONES_CLIENT_KEY, AGONES_CA_CERT])

            if use_tls:
                logger.info("Using TLS certificates for Agones Allocator")
                response = requests.post(
                    self.agones_allocator_url,
                    json=allocation_request,
                    headers={'Content-Type': 'application/json'},
                    cert=(AGONES_CLIENT_CERT, AGONES_CLIENT_KEY),
                    verify=AGONES_CA_CERT,
                    timeout=10
                )
            else:
                logger.warning("TLS certificates not found, using insecure connection (development only!)")
                response = requests.post(
                    self.agones_allocator_url,
                    json=allocation_request,
                    headers={'Content-Type': 'application/json'},
                    verify=False,
                    timeout=10
                )

            if response.status_code not in [200, 201]:
                logger.error(f"Failed to allocate GameServer: {response.status_code} - {response.text}")
                return None

            result = response.json()

            status = result.get('status', {})
            address = status.get('address', '')
            ports = status.get('ports', [])

            if not address or not ports:
                logger.error("GameServer allocation missing address or ports")
                return None

            game_port = None
            for port in ports:
                if port.get('name') == 'game' or not game_port:
                    game_port = port.get('port')

            if not game_port:
                logger.error("No game port found in allocation")
                return None

            connection = f"{address}:{game_port}"
            logger.info(f"Allocated GameServer: {connection}")

            return {
                'address': address,
                'port': game_port,
                'connection': connection
            }

        except Exception as e:
            logger.error(f"Error allocating GameServer: {e}", exc_info=True)
            return None

    def assign_tickets(self, match: messages_pb2.Match, connection_string: str) -> bool:
        try:
            ticket_ids = [ticket.id for ticket in match.tickets]

            if not ticket_ids:
                logger.warning("No tickets to assign")
                return False

            logger.info(f"Assigning {len(ticket_ids)} tickets to {connection_string}...")

            assignment = messages_pb2.Assignment(connection=connection_string)
            assignment_group = backend_pb2.AssignmentGroup(
                ticket_ids=ticket_ids,
                assignment=assignment
            )

            channel = grpc.insecure_channel(self.backend_addr)
            stub = backend_pb2_grpc.BackendServiceStub(channel)

            request = backend_pb2.AssignTicketsRequest(assignments=[assignment_group])
            response = stub.AssignTickets(request, timeout=10)

            channel.close()

            logger.info(f"Successfully assigned tickets {ticket_ids}")
            return True

        except grpc.RpcError as e:
            logger.error(f"gRPC error assigning tickets: {e.code()} - {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Error assigning tickets: {e}", exc_info=True)
            return False

    def run_cycle(self):
        try:
            logger.info("=" * 60)
            logger.info("Starting matchmaking cycle")

            profile = self.create_match_profile()
            matches = self.fetch_matches(profile)

            if not matches:
                logger.info("No matches found this cycle")
                return

            for match in matches:
                logger.info(f"Processing match {match.match_id}...")

                allocation = self.allocate_game_server()

                if not allocation:
                    logger.warning(f"Failed to allocate GameServer for match {match.match_id}, skipping")
                    continue

                connection = allocation['connection']
                success = self.assign_tickets(match, connection)

                if success:
                    logger.info(f"Successfully completed match {match.match_id} -> {connection}")
                else:
                    logger.warning(f"Failed to assign tickets for match {match.match_id}")

        except Exception as e:
            logger.error(f"Error in matchmaking cycle: {e}", exc_info=True)

    def run(self):
        logger.info("Director starting...")
        logger.info(f"Fetch interval: {FETCH_INTERVAL}s")

        # insecureモード時はSSL警告を無効化
        use_tls = all(os.path.exists(f) for f in [AGONES_CLIENT_CERT, AGONES_CLIENT_KEY, AGONES_CA_CERT])
        if not use_tls:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        while True:
            try:
                self.run_cycle()
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)

            time.sleep(FETCH_INTERVAL)


if __name__ == '__main__':
    director = Director()
    director.run()
