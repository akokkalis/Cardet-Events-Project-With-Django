from django import template
from django.template.defaultfilters import stringfilter
from decimal import Decimal

register = template.Library()


@register.filter(name="get_item")
def get_item(dictionary, key):
    """Get an item from a dictionary using template variables."""
    return dictionary.get(key)


@register.filter(name="filter")
def filter_queryset(queryset, filter_string):
    """Filter a queryset based on a field=value string."""
    try:
        field, value = filter_string.split("=")
        # Remove quotes from value if present
        value = value.strip("'\"")
        filter_dict = {field: value}
        return [item for item in queryset if getattr(item, field, None) == value]
    except (ValueError, AttributeError):
        return []


@register.filter(name="euro")
def euro(value):
    """Format a numeric value as euro currency."""
    if value is None:
        return "€0.00"

    try:
        # Convert to Decimal for precise formatting
        if isinstance(value, str):
            # Remove any existing currency symbols
            clean_value = (
                value.replace("$", "")
                .replace("€", "")
                .replace("£", "")
                .replace("¥", "")
                .replace("₹", "")
                .strip()
            )
            decimal_value = Decimal(clean_value)
        else:
            decimal_value = Decimal(str(value))

        # Format with 2 decimal places
        return f"€{decimal_value:.2f}"
    except (ValueError, TypeError, ArithmeticError):
        return "€0.00"
