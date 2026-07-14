from dataclasses import dataclass


@dataclass
class Event:

    event_type: str

    field: str

    old_value: str

    new_value: str