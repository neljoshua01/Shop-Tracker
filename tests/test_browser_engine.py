from services.async_runtime import AsyncRuntime
from services.browser_engine import BrowserEngine


runtime = AsyncRuntime.instance()

future = runtime.submit(

    BrowserEngine.instance().open_page(
        "https://example.com"
    )

)

page = future.result(timeout=20)

title = runtime.submit(
    page.title()
).result(timeout=10)

print(title)

runtime.submit(
    BrowserEngine.instance().close_page(page)
).result(timeout=10)

print("Async page test passed.")