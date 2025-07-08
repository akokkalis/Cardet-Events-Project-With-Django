from django import template
from django.template.defaultfilters import stringfilter

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
