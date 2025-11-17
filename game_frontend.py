#!/usr/bin/env python3

import logging
import os
import sys
from flask import Flask, request, jsonify
import grpc
from typing import Optional
import jwt
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64
import json

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
JWT_EXPIRATION_MINUTES = int(os.getenv('JWT_EXPIRATION_MINUTES', '60'))

app = Flask(__name__)

PRIVATE_KEY = None
PUBLIC_KEY = None
PUBLIC_KEY_PEM = None


def generate_rsa_keypair():
    global PRIVATE_KEY, PUBLIC_KEY, PUBLIC_KEY_PEM

    logger.info("Generating RSA key pair...")

    PRIVATE_KEY = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    PUBLIC_KEY = PRIVATE_KEY.public_key()

    PUBLIC_KEY_PEM = PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    logger.info("RSA key pair generated successfully")


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

    private_pem = PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    token = jwt.encode(payload, private_pem, algorithm='RS256')
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


def get_jwks():
    public_numbers = PUBLIC_KEY.public_numbers()

    def int_to_base64url(value):
        value_bytes = value.to_bytes((value.bit_length() + 7) // 8, byteorder='big')
        return base64.urlsafe_b64encode(value_bytes).rstrip(b'=').decode('utf-8')

    jwk = {
        'kty': 'RSA',
        'use': 'sig',
        'kid': 'game-frontend-key-1',
        'alg': 'RS256',
        'n': int_to_base64url(public_numbers.n),
        'e': int_to_base64url(public_numbers.e)
    }

    return {'keys': [jwk]}


@app.route('/.well-known/jwks.json', methods=['GET'])
def jwks():
    """公開鍵をJWKS形式で返す"""
    return jsonify(get_jwks()), 200


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
    logger.info(f"JWT Algorithm: RS256 (Public Key Authentication)")
    logger.info("=" * 60)

    generate_rsa_keypair()

    logger.info("=" * 60)
    logger.info("Server ready to accept requests")
    logger.info("Endpoints:")
    logger.info(f"  - GET  /health")
    logger.info(f"  - GET  /play/<region>")
    logger.info(f"  - GET  /.well-known/jwks.json (Public Key)")
    logger.info("=" * 60)

    app.run(host='0.0.0.0', port=PORT, debug=False)
