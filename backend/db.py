"""FalkorDB connection helpers for MuleTrace."""
import os

from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()


def get_graph():
    """Return a FalkorDB Graph object for GRAPH_NAME, reading config from .env."""
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    graph_name = os.getenv("GRAPH_NAME", "muletrace")

    db = FalkorDB(host=host, port=port)
    return db.select_graph(graph_name)