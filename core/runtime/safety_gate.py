"""Runtime authorization for a future irreversible checkout action."""


class RuntimeSafetyGate:
    """Application-wide Armed/Safe state, always SAFE when constructed."""

    _instance = None

    def __init__(self):
        self._armed = False

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reset_to_safe(self):
        self._armed = False

    def set_armed(self, armed):
        # Only the literal boolean True can authorize the future action.
        self._armed = armed is True

    def is_armed(self):
        return self._armed is True

    def is_final_action_authorized(self):
        try:
            return self.is_armed() is True
        except Exception:
            return False
