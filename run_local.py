import threading
import webbrowser

import uvicorn

from app.core.config import settings
from app.db.database import init_db


def open_browser() -> None:
    webbrowser.open(f"http://127.0.0.1:{settings.server_port}")


if __name__ == "__main__":
    init_db()
    threading.Timer(1.2, open_browser).start()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.server_port,
        reload=False,
    )
