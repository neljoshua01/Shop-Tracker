"""UI-facing operations for the application runtime safety gate."""


def set_armed_mode(safety_gate, armed):
    """Apply an explicit toggle choice; this never starts checkout work."""
    safety_gate.set_armed(bool(armed))
    return safety_gate.is_armed()
