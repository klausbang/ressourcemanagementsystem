import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Defaults are unchanged (127.0.0.1, debug on) - local-only, exactly as before.
    # Set HOST=0.0.0.0 (proposal id 8: sharing this dev instance with someone on another
    # network) to accept connections from other machines - see README.md "Sharing this
    # app during development" for how to actually reach it from outside your network,
    # and the security tradeoffs of doing so, before setting this.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug_env = os.environ.get("DEBUG")
    if debug_env is not None:
        # Explicit override - needed for e.g. a tunnel (ngrok/Cloudflare Tunnel) that
        # makes a 127.0.0.1-bound instance internet-reachable anyway, which the
        # HOST-based default below can't see coming.
        debug = debug_env.strip().lower() in ("1", "true", "yes", "on")
    else:
        debug = host == "127.0.0.1"  # never run Werkzeug's interactive debugger while reachable from outside this machine - see the README
    app.run(host=host, port=port, debug=debug)
