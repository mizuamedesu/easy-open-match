#!/usr/bin/env python3

import logging
import time
import os
import sys
import grpc
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from protos.api import frontend_pb2
from protos.api import frontend_pb2_grpc
from protos.api import messages_pb2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OPEN_MATCH_FRONTEND_SERVICE = os.getenv(
    'OPEN_MATCH_FRONTEND_SERVICE',
    'open-match-frontend.open-match.svc.cluster.local:50504'
)

ASSIGNMENT_TIMEOUT = int(os.getenv('ASSIGNMENT_TIMEOUT', '60'))
POLL_INTERVAL = 1


class MatchmakingClient:

    def __init__(self):
        self.frontend_addr = OPEN_MATCH_FRONTEND_SERVICE
        logger.info(f"Frontend service: {self.frontend_addr}")

    def create_ticket_and_wait(self) -> tuple[Optional[str], Optional[str]]:
        """
        チケット作成とアサインメント待機を同じチャネルで実行
        OpenMatchではCreateTicket後すぐにWatchAssignmentsを呼び出す必要がある
        """
        channel = None
        ticket_id = None

        try:
            channel = grpc.insecure_channel(self.frontend_addr)
            stub = frontend_pb2_grpc.FrontendServiceStub(channel)

            # チケット作成
            ticket = messages_pb2.Ticket(
                search_fields=messages_pb2.SearchFields(tags=[])
            )
            request = frontend_pb2.CreateTicketRequest(ticket=ticket)
            logger.info("Creating ticket...")
            response = stub.CreateTicket(request, timeout=10)
            ticket_id = response.id
            logger.info(f"Created ticket: {ticket_id}")

            # 同じチャネルでアサインメント待機
            logger.info(f"Waiting for assignment (timeout: {ASSIGNMENT_TIMEOUT}s)...")
            watch_request = frontend_pb2.WatchAssignmentsRequest(ticket_id=ticket_id)

            try:
                response_iterator = stub.WatchAssignments(watch_request, timeout=ASSIGNMENT_TIMEOUT)
                for response in response_iterator:
                    if response.assignment and response.assignment.connection:
                        connection = response.assignment.connection
                        logger.info(f"Assignment received: {connection}")
                        return ticket_id, connection

            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    logger.warning("Timeout waiting for assignment")
                else:
                    logger.error(f"gRPC error watching assignments: {e.code()} - {e.details()}")

            return ticket_id, None

        except grpc.RpcError as e:
            logger.error(f"gRPC error: {e.code()} - {e.details()}")
            return ticket_id, None
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return ticket_id, None
        finally:
            if channel:
                channel.close()

    def get_ticket(self, ticket_id: str) -> Optional[messages_pb2.Ticket]:
        try:
            channel = grpc.insecure_channel(self.frontend_addr)
            stub = frontend_pb2_grpc.FrontendServiceStub(channel)

            request = frontend_pb2.GetTicketRequest(ticket_id=ticket_id)
            response = stub.GetTicket(request, timeout=10)

            channel.close()

            return response

        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.NOT_FOUND:
                logger.error(f"gRPC error getting ticket: {e.code()} - {e.details()}")
            return None
        except Exception as e:
            logger.error(f"Error getting ticket: {e}", exc_info=True)
            return None

    def delete_ticket(self, ticket_id: str) -> bool:
        try:
            channel = grpc.insecure_channel(self.frontend_addr)
            stub = frontend_pb2_grpc.FrontendServiceStub(channel)

            request = frontend_pb2.DeleteTicketRequest(ticket_id=ticket_id)
            stub.DeleteTicket(request, timeout=10)

            channel.close()

            logger.info(f"Deleted ticket: {ticket_id}")
            return True

        except grpc.RpcError as e:
            logger.error(f"gRPC error deleting ticket: {e.code()} - {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Error deleting ticket: {e}", exc_info=True)
            return False

    def run(self):
        logger.info("=" * 60)
        logger.info("OpenMatch Matchmaking Test Client (gRPC)")
        logger.info("=" * 60)

        ticket_id, connection = self.create_ticket_and_wait()

        if not ticket_id:
            logger.error("Failed to create ticket")
            return 1

        try:
            if connection:
                logger.info("=" * 60)
                logger.info(f"SUCCESS! Match found!")
                logger.info(f"Game Server: {connection}")
                logger.info("=" * 60)
                return 0
            else:
                logger.error("=" * 60)
                logger.error("TIMEOUT! No match found")
                logger.error("=" * 60)
                return 1

        finally:
            logger.info("Cleaning up...")
            self.delete_ticket(ticket_id)


if __name__ == '__main__':
    client = MatchmakingClient()
    exit_code = client.run()
    sys.exit(exit_code)
