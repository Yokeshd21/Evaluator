import os
import phoenix as px
from phoenix.otel import register

def start_tracing():
    """
    Launches the Phoenix app locally and registers the OpenTelemetry exporter.
    Forces local connection to avoid 'app.arize.com' connection issues.
    """
    try:
        # Launch Phoenix locally
        session = px.active_session()
        if not session:
            # Explicitly launch locally
            session = px.launch_app()
        
        # Register local OpenTelemetry pointing explicitly to the local Phoenix server
        # Default Phoenix port is 6006
        register(
            project_name="Evaluator",
            endpoint="http://localhost:6006/v1/traces",
            auto_instrument=True,
        )
        
        # Ensure we return the local URL for the iframe
        return session.url if session else "http://localhost:6006"
        
    except Exception as e:
        print(f"Phoenix Tracing Error: {e}")
        return "http://localhost:6006"
