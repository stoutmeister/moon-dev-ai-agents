"""Minimal base class for the skip tracer + dialer agents."""
from datetime import datetime


class BaseAgent:
    def __init__(self, agent_type):
        self.type = agent_type
        self.start_time = datetime.now()

    def run(self):
        raise NotImplementedError("Each agent must implement its own run method")
