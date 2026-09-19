import asyncio

from execution.browser.browser_engine import BrowserEngine


class FakeResponse:
    url = "https://shopee.ph/api/v4/pdp/get_pc"
    status = 200

    def __init__(self, body=b'{"data": {"item": 1}}'):
        self._body = body
        self.body_started = False
        self.body_finished = False

    async def body(self):
        self.body_started = True
        await asyncio.sleep(0)
        self.body_finished = True
        return self._body


def test_get_pc_body_is_captured_before_two_argument_callback_runs():
    engine = BrowserEngine()
    response = FakeResponse()
    observations = []

    async def callback(received_response, body):
        observations.append(
            (
                received_response is response,
                response.body_started,
                response.body_finished,
                body,
            )
        )

    async def run():
        await engine._capture_and_dispatch_response(
            response,
            [callback],
        )
        await asyncio.sleep(0)

    asyncio.run(run())

    assert observations == [
        (True, True, True, b'{"data": {"item": 1}}')
    ]


def test_get_pc_body_capture_preserves_one_argument_callback_contract():
    engine = BrowserEngine()
    response = FakeResponse()
    received = []

    async def callback(received_response):
        received.append(received_response)

    async def run():
        await engine._capture_and_dispatch_response(
            response,
            [callback],
        )
        await asyncio.sleep(0)

    asyncio.run(run())

    assert received == [response]
