from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Django getter to allow HTML pages to use dictionaries."""
    return dictionary.get(key)
