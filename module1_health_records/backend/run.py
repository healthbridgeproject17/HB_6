import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # The interactive debugger lets anyone who reaches the page run code, so it
    # is OFF unless you explicitly set FLASK_DEBUG=1 on your own machine.
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=5000)
