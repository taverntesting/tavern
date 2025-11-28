import json
import logging
import queue
import threading
import uuid
from collections import defaultdict
from typing import Any, Optional

import websockets
import websockets.sync.client
from _plugins.common.response import ResponseLike
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import ExecutionResult

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponseLike(ResponseLike):
    """A response-like object implementing the ResponseLike protocol for GraphQL responses"""

    def __init__(self, status_code: int, reason: str, headers: dict, text: str):
        self.status_code = status_code
        self.reason = reason
        self.headers = headers
        self.text = text
        self._json = None

    def json(self) -> Any:
        """Parse and return the JSON content of the response"""
        if self._json is None:
            try:
                self._json = json.loads(self.text)
            except ValueError as e:
                raise ValueError(
                    f"Response content is not valid JSON: {self.text}"
                ) from e
        return self._json


class GraphQLClient:
    """GraphQL client for HTTP requests and subscriptions over WebSocket"""

    ws: websockets.sync.client.ClientConnection | None

    def __init__(self, **kwargs):
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)

        # WS for subscriptions
        self.ws = None
        self.recv_thread = None
        self.op_to_id: dict[str, str] = {}
        self.id_to_op: dict[str, str] = {}
        self.sub_queues: defaultdict[str, queue.Queue] = defaultdict(queue.Queue)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_ws()

    def update_session(self, **kwargs):
        """Update session with new configuration"""
        if "headers" in kwargs:
            self.default_headers.update(kwargs["headers"])

    def make_request(
        self,
        url: str,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        method: str = "POST",
    ) -> ResponseLike:
        """Execute GraphQL query/mutation over HTTP using gql"""
        if method.upper() == "GET":
            raise NotImplementedError(
                "GET method not supported with gql transport. Use POST."
            )

        headers = dict(self.default_headers)
        headers["Content-Type"] = "application/json"

        transport = AIOHTTPTransport(
            url=url,
            headers=headers,
            timeout=self.timeout,
        )
        client = Client(transport=transport)

        query_gql = gql(query)

        try:
            result: ExecutionResult = client.execute(
                query_gql,
                variable_values=variables or {},
                operation_name=operation_name,
                get_execution_result=True,
            )
            body_dict = {}
            if result.data:
                body_dict["data"] = result.data
            if result.errors:
                body_dict["errors"] = result.errors
            text = json.dumps(body_dict)
            status_code = 200
            reason = "OK"
        except Exception as exc:
            status_code = 500
            reason = "Internal Server Error"
            body_dict = {"errors": [{"message": str(exc)}]}
            text = json.dumps(body_dict)

        response_headers = {"Content-Type": "application/json"}

        return GraphQLResponseLike(status_code, reason, response_headers, text)

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
