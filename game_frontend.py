#!/usr/bin/env python3

import logging
import os
import sys
from flask import Flask, request, jsonify
import grpc
from typing import Optional
import jwt
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from protos.api import frontend_pb2
from protos.api import frontend_pb2_grpc
from protos.api import messages_pb2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
OPEN_MATCH_FRONTEND_SERVICE = os.getenv(
    'OPEN_MATCH_FRONTEND_SERVICE',
    'open-match-frontend.open-match.svc.cluster.local:50504'
)
ASSIGNMENT_TIMEOUT = int(os.getenv('ASSIGNMENT_TIMEOUT', '60'))
BEARER_TOKEN = os.getenv('BEARER_TOKEN', 'secret-token-12345')
PORT = int(os.getenv('PORT', '8080'))
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_EXPIRATION_MINUTES = int(os.getenv('JWT_EXPIRATION_MINUTES', '60'))

app = Flask(__name__)


def check_auth(auth_header: Optional[str]) -> bool:
    """Bearer トークン認証"""
    if not auth_header:
        return False

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return False

    return parts[1] == BEARER_TOKEN


def generate_jwt(ticket_id: str, server_info: dict, player_info: dict) -> str:
    """JWT生成"""
    now = datetime.utcnow()
    expiration = now + timedelta(minutes=JWT_EXPIRATION_MINUTES)

    payload = {
        'ticket_id': ticket_id,
        'server': server_info,
        'player': player_info,
        'iat': now,
        'exp': expiration
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
    return token


def create_ticket(region: str) -> messages_pb2.Ticket:
    """チケット作成"""
    import random
    import time

    random.seed(time.time())
    skill = 2 * random.random()
    latency = 50.0 * random.expovariate(1.0)

    ticket = messages_pb2.Ticket(
        search_fields=messages_pb2.SearchFields(
            tags=["mode.session"],
            double_args={
                "skill": skill,
                "latency": latency
            },
            string_args={
                "region": region
            }
        )
    )
    return ticket


def get_assignment(ticket_id: str) -> Optional[dict]:
    """アサインメント取得"""
    try:
        channel = grpc.insecure_channel(OPEN_MATCH_FRONTEND_SERVICE)
        stub = frontend_pb2_grpc.FrontendServiceStub(channel)

        watch_request = frontend_pb2.WatchAssignmentsRequest(ticket_id=ticket_id)

        try:
            response_iterator = stub.WatchAssignments(watch_request, timeout=ASSIGNMENT_TIMEOUT)
            for response in response_iterator:
                if response.assignment and response.assignment.connection:
                    connection = response.assignment.connection
                    parts = connection.split(':')
                    channel.close()
                    return {
                        'ip': parts[0],
                        'port': parts[1] if len(parts) > 1 else '',
                        'connection': connection
                    }
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                logger.warning(f"Timeout waiting for assignment: {ticket_id}")
            else:
                logger.error(f"gRPC error: {e.code()} - {e.details()}")

        channel.close()
        return None

    except Exception as e:
        logger.error(f"Error getting assignment: {e}", exc_info=True)
        return None


@app.route('/health', methods=['GET'])
def health():
    """ヘルスチェック"""
    return jsonify({'status': 'ok'}), 200


@app.route('/play/<region>', methods=['GET'])
def play(region: str):
    """マッチング開始"""
    # 認証チェック
    auth_header = request.headers.get('Authorization')
    if not check_auth(auth_header):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # チケット作成
        ticket = create_ticket(region)

        channel = grpc.insecure_channel(OPEN_MATCH_FRONTEND_SERVICE)
        stub = frontend_pb2_grpc.FrontendServiceStub(channel)

        req = frontend_pb2.CreateTicketRequest(ticket=ticket)
        resp = stub.CreateTicket(request=req, timeout=10)
        ticket_id = resp.id

        logger.info(f"Created ticket: {ticket_id}, region: {region}")

        # アサインメント待機
        assignment = get_assignment(ticket_id)

        if assignment:
            server_info = {
                'ip': assignment['ip'],
                'port': assignment['port'],
                'connection': assignment['connection']
            }
            player_info = {
                'skill': ticket.search_fields.double_args['skill'],
                'latency': ticket.search_fields.double_args['latency'],
                'region': region
            }

            # JWT生成
            access_token = generate_jwt(ticket_id, server_info, player_info)

            result = {
                'status': 'matched',
                'ticket_id': ticket_id,
                'server': server_info,
                'player': player_info,
                'jwt': access_token
            }
            logger.info(f"Match found for ticket {ticket_id}: {assignment['connection']}")
            return jsonify(result), 200
        else:
            result = {
                'status': 'timeout',
                'ticket_id': ticket_id,
                'message': 'No match found within timeout period'
            }
            logger.warning(f"Timeout for ticket {ticket_id}")
            return jsonify(result), 408

    except grpc.RpcError as e:
        logger.error(f"gRPC error: {e.code()} - {e.details()}")
        return jsonify({'error': f'gRPC error: {e.details()}'}), 500
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Game Frontend HTTP API Server")
    logger.info(f"OpenMatch Frontend: {OPEN_MATCH_FRONTEND_SERVICE}")
    logger.info(f"Port: {PORT}")
    logger.info(f"Bearer Token: {'*' * len(BEARER_TOKEN)}")
    logger.info(f"JWT Expiration: {JWT_EXPIRATION_MINUTES} minutes")
    logger.info(f"JWT Secret Key: {'*' * len(JWT_SECRET_KEY)}")
    logger.info("=" * 60)

    app.run(host='0.0.0.0', port=PORT, debug=False)
