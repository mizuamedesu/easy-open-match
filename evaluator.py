#!/usr/bin/env python3

import logging
import grpc
from concurrent import futures
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from protos.api import evaluator_pb2
from protos.api import evaluator_pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EvaluatorServicer(evaluator_pb2_grpc.EvaluatorServicer):


    def Evaluate(self, request_iterator, context):
        try:
            for request in request_iterator:
                # マッチ提案をそのまま返す
                response = evaluator_pb2.EvaluateResponse(
                    match=request.match
                )
                yield response

        except Exception as e:
            logger.error(f"Error in Evaluator.Evaluate: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f'Internal error: {str(e)}')


def serve_grpc(port=50508):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    evaluator_pb2_grpc.add_EvaluatorServicer_to_server(
        EvaluatorServicer(), server
    )

    server.add_insecure_port(f'[::]:{port}')

    logger.info(f"Evaluator gRPC server starting on port {port}")
    server.start()

    logger.info("Evaluator server ready")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop(grace=5)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='OpenMatch Pass-through Evaluator (gRPC)')
    parser.add_argument('--port', type=int, default=50508, help='Port to listen on')

    args = parser.parse_args()

    logger.info("Starting Evaluator gRPC server...")
    logger.info(f"Port: {args.port}")

    serve_grpc(args.port)
