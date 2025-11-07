#!/usr/bin/env python3

import logging
import time
import grpc
from concurrent import futures
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from protos.api import matchfunction_pb2
from protos.api import matchfunction_pb2_grpc
from protos.api import messages_pb2
from protos.api import query_pb2
from protos.api import query_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

QUERY_SERVICE_HOST = os.getenv('OPEN_MATCH_QUERY_SERVICE', 'open-match-query.open-match.svc.cluster.local')
QUERY_SERVICE_PORT = os.getenv('OPEN_MATCH_QUERY_SERVICE_PORT', '50503')


class MatchFunctionServicer(matchfunction_pb2_grpc.MatchFunctionServicer):

    def __init__(self):
        self.query_service_addr = f'{QUERY_SERVICE_HOST}:{QUERY_SERVICE_PORT}'
        logger.info(f"MatchFunction will query tickets from: {self.query_service_addr}")

    def _query_tickets(self, pool):
        try:
            channel = grpc.insecure_channel(self.query_service_addr)
            stub = query_pb2_grpc.QueryServiceStub(channel)

            request = query_pb2.QueryTicketsRequest(pool=pool)
            response_iterator = stub.QueryTickets(request, timeout=10)

            tickets = []
            for response in response_iterator:
                tickets.append(response.ticket)

            channel.close()
            logger.info(f"Queried {len(tickets)} tickets from pool '{pool.name}'")
            return tickets

        except grpc.RpcError as e:
            logger.error(f"gRPC error querying tickets: {e.code()} - {e.details()}")
            return []
        except Exception as e:
            logger.error(f"Error querying tickets: {e}", exc_info=True)
            return []

    def Run(self, request, context):
        try:
            logger.info("MatchFunction.Run called")

            profile = request.profile
            logger.info(f"Match profile: {profile.name}")
            logger.info(f"Number of pools: {len(profile.pools)}")

            # 全プールからチケットを収集
            all_tickets = []
            for pool in profile.pools:
                tickets = self._query_tickets(pool)
                all_tickets.extend(tickets)

            logger.info(f"Total tickets to process: {len(all_tickets)}")

            # 2人マッチを作成
            if len(all_tickets) >= 2:
                ticket1 = all_tickets[0]
                ticket2 = all_tickets[1]

                match_id = f"match-{int(time.time())}"

                match = messages_pb2.Match(
                    match_id=match_id,
                    match_profile=profile.name,
                    match_function="matchfunction",
                    tickets=[ticket1, ticket2]
                )

                logger.info(f"Created match {match_id} with tickets: {ticket1.id}, {ticket2.id}")

                response = matchfunction_pb2.RunResponse(proposal=match)
                yield response

            else:
                logger.info("Not enough tickets for a 2-player match")
                yield matchfunction_pb2.RunResponse()

        except Exception as e:
            logger.error(f"Error in MatchFunction.Run: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f'Internal error: {str(e)}')
            yield matchfunction_pb2.RunResponse()


def serve_grpc(port=50502):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    matchfunction_pb2_grpc.add_MatchFunctionServicer_to_server(
        MatchFunctionServicer(), server
    )

    server.add_insecure_port(f'[::]:{port}')

    logger.info(f"MatchFunction gRPC server starting on port {port}")
    server.start()

    logger.info("MatchFunction server ready")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop(grace=5)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='OpenMatch MatchFunction (gRPC)')
    parser.add_argument('--port', type=int, default=50502, help='Port to listen on')

    args = parser.parse_args()

    logger.info("Starting MatchFunction gRPC server...")
    logger.info(f"Port: {args.port}")

    serve_grpc(args.port)
