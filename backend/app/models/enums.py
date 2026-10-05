from enum import StrEnum


def enum_values[EnumType: StrEnum](enum_class: type[EnumType]) -> list[str]:
    return [member.value for member in enum_class]


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class GoalType(StrEnum):
    LOSE = "lose_weight"
    MAINTAIN = "maintain_weight"
    GAIN = "gain_weight"


class PantryStatus(StrEnum):
    AVAILABLE = "available"
    LOW = "low"
    UNAVAILABLE = "unavailable"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    GENERATED = "generated"
    READ = "read"
    FAILED = "failed"
