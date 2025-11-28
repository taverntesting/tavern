import json
import logging
import queue
import threading
import uuid
from collections import defaultdict
from typing import Any, Optional

import requests
import websockets
import websockets.sync.client

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLClient:
    """GraphQL client for HTTP requests and subscriptions over WebSocket"""

    ws: websockets.sync.client.ClientConnection | None

    def __init__(self, **kwargs):
        self.session = requests.Session()
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)

        # WS for subscriptions
        self.ws = None
        self.recv_thread = None
        self.op_to_id: dict[str, str] = {}
        self.id_to_op: dict[str, str] = {}
        self.sub_queues: defaultdict[str, queue.Queue] = defaultdict(queue.Queue)

    def __enter__(self):
        return self.session.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_ws()
        self.session.__exit__(exc_type, exc_val, exc_tb)

    def update_session(self, **kwargs):
        """Update session with new configuration"""
        if "headers" in kwargs:
            self.session.headers.update(kwargs["headers"])

    def make_request(
        self,
        url: str,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        method: str = "POST",
    ) -> requests.Response:
        """Execute GraphQL query/mutation over HTTP using raw requests"""
        payload = {
            "query": query,
            "variables": variables or {},
        }

        if operation_name:
            payload["operationName"] = operation_name

        headers = dict(self.default_headers)
        headers.update({"Content-Type": "application/json"})

        if method.upper() == "GET":
            params = {"query": query}
            if variables:
                params["variables"] = json.dumps(variables)
            if operation_name:
                params["operationName"] = operation_name

            return self.session.get(
                url, params=params, headers=headers, timeout=self.timeout
            )
        else:
            return self.session.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )

    def _ws_recv_loop(self):
        """Daemon thread to receive WS messages and dispatch to sub queues"""
        while self.ws:
            try:
                msg_str = self.ws.recv()
                msg = json.loads(msg_str)
                msg_type = msg.get("type")

                if msg_type == "connection_ack":
                    logger.debug("WS connection acknowledged")
                elif msg_type == "data":
                    id_ = msg["id"]
                    if id_ in self.id_to_op:
                        op = self.id_to_op[id_]
                        payload = msg["payload"]
                        self.sub_queues[op].put(payload)
                        logger.debug(f"Dispatched data for sub {op}")
                elif msg_type == "complete":
                    id_ = msg["id"]
                    logger.debug(f"Subscription complete: {id_}")
                elif msg_type == "error":
                    logger.error(f"WS error: {msg}")
                elif msg_type == "ka":
                    self.ws.send(json.dumps({"id": msg["id"], "type": "ka"}))
                else:
                    logger.debug(f"WS msg: {msg}")
            except websockets.ConnectionClosedError:
                break
            except Exception as e:
                logger.error(f"WS recv error: {e}")
                break

    def start_subscription(
        self, url: str, query: str, variables: dict, operation_name: str
    ) -> str:
        """Start a GraphQL subscription over WS"""
        if operation_name is None:
            raise ValueError("operation_name required for subscriptions")

        if self.ws is None:
            ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
            logger.debug(f"Starting WS connection to {ws_url}")
            self.ws = websockets.sync.client.connect(ws_url)
            self.ws.send(json.dumps({"type": "connection_init", "payload": {}}))
            ack = json.loads(self.ws.recv())
            if ack.get("type") != "connection_ack":
                raise RuntimeError(f"WS connection failed: {ack}")
            self.recv_thread = threading.Thread(target=self._ws_recv_loop, daemon=True)
            self.recv_thread.start()
            logger.debug("WS connection started")

        id_ = str(uuid.uuid4())
        self.op_to_id[operation_name] = id_
        self.id_to_op[id_] = operation_name

        payload = {
            "query": query,
            "variables": variables,
            "operationName": operation_name,
        }
        self.ws.send(json.dumps({"id": id_, "type": "start", "payload": payload}))
        logger.debug(f"Started subscription {operation_name} id {id_}")
        return id_

    def get_next_message(
        self, operation_name: str, timeout: float = 5.0
    ) -> Optional[dict]:
        """Get next message from subscription queue"""
        try:
            return self.sub_queues[operation_name].get(timeout=timeout)
        except queue.Empty:
            return None

    def _close_ws(self):
        """Close WS connection"""
        if self.ws:
            self.ws.send(json.dumps({"type": "connection_terminate"}))
            self.ws.close()
            self.ws = None
            self.sub_queues.clear()
            self.op_to_id.clear()
            self.id_to_op.clear()
            logger.debug("WS connection closed")
