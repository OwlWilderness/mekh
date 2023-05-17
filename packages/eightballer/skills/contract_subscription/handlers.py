# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 eightballer
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains a scaffold of a handler."""

import json
import time

from aea.protocols.base import Message
from aea.skills.base import Handler
from web3 import Web3

from packages.fetchai.protocols.default.message import DefaultMessage

JOB_QUEUE = "pending_tasks"

DEFAULT_CONTRACT = "0xFf82123dFB52ab75C417195c5fDB87630145ae81"
DEFAULT_ENDPOINT = "https://rpc.gnosischain.com"


class WebSocketHandler(Handler):
    """This class scaffolds a handler."""

    SUPPORTED_PROTOCOL = DefaultMessage.protocol_id
    w3: Web3 = None
    contract = None

    def setup(self) -> None:
        """Implement the setup."""
        self.context.shared_state[JOB_QUEUE] = []
        # loads the contracts from the config file
        with open("vendor/valory/contracts/agent_mech/build/AgentMech.json", "r", encoding="utf-8") as file:
            abi = json.load(file)['abi']

        self.w3 = Web3(Web3.HTTPProvider(DEFAULT_ENDPOINT))  # pylint: disable=C0103
        self.contract = self.w3.eth.contract(address=DEFAULT_CONTRACT, abi=abi)

    def handle(self, message: Message) -> None:
        """
        Implement the reaction to an envelope.

        :param message: the message
        """
        self.context.logger.info(f"Received message: {message}")
        data = json.loads(message.content)
        if set(data.keys()) == {"id", "result", "jsonrpc"}:
            self.context.logger.info(f"Received subscription response: {data}")
            return

        self.context.logger.info("Extracting data")
        tx_hash = data['params']['result']['transactionHash']
        no_args = True
        limit = 0
        while no_args and limit < 10:
            event_args, no_request = self._get_tx_args(tx_hash)
            if no_request:
                self.context.logger.info("Event not a Request.")
                break
            if len(event_args) == 0:
                self.context.logger.info(f"Could not get event args. tx_hash={tx_hash}")
                time.sleep(1)
                limit += 1
                return
            no_args = False
        self.context.shared_state[JOB_QUEUE].append(event_args)
        self.context.logger.info(f"Added job to queue: {event_args}")

    def teardown(self) -> None:
        """Implement the handler teardown."""

    def _get_tx_args(self, tx_hash: str):
        """Get the transaction arguments."""
        try:
            tx_receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            rich_logs = self.contract.events.Request().processReceipt(tx_receipt)  # type: ignore
            return dict(rich_logs[0]['args']), False

        except Exception:  # pylint: disable=W0718
            return {}, True
