"""Turns a stream of per-window scores into alerts. One high score is not an alert:
it takes k high windows out of the last m, and after an alert there is a quiet
period (cooldown) so one incident does not raise dozens of alerts."""
from collections import deque


class AlertRule:
    def __init__(self, k=2, m=3, cooldown=12):
        if not 1 <= k <= m:
            raise ValueError("k must be between 1 and m")
        self.k, self.m, self.cooldown = k, m, cooldown

    def state(self):
        return AlertState(self)

    def alerts(self, above):
        """above: sequence of booleans (score >= threshold). Returns the window indexes where an alert is raised."""
        state, out = self.state(), []
        for i, flag in enumerate(above):
            if state.update(bool(flag)):
                out.append(i)
        return out

    def as_dict(self):
        return {"k": self.k, "m": self.m, "cooldown": self.cooldown}


class AlertState:
    """The streaming version used by the live monitor, one per machine."""

    def __init__(self, rule):
        self.rule, self.recent, self.quiet = rule, deque(maxlen=rule.m), 0

    def update(self, above: bool) -> bool:
        self.recent.append(above)
        if self.quiet > 0:
            self.quiet -= 1
            return False
        if sum(self.recent) >= self.rule.k:
            self.quiet = self.rule.cooldown
            return True
        return False
